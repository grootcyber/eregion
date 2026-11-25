// ── The console's header (console.js) ─────────────────────────────────────────
// This page is Glorfindel's section (/glorfindel), or its configuration (/config). The live
// feed's dot belongs to this page: it sits on the LIVE FEED column, not in the shared header.
const _IS_CONFIG = location.pathname.replace(/\/+$/, '') === '/config';
// MBV1: the header's « ⚡ model breaker » opens the watch's cards here, without leaving the page.
Console.init(_IS_CONFIG ? 'config' : 'glorfindel', { onBreaker: () => openWatchCards() });
if (_IS_CONFIG) document.title = 'Eregion — Config';
// ?card=<id> (a link from Annatar's or Gothmog's page): that card, highlighted in TO JUDGE.
let _focusCard = new URLSearchParams(location.search).get('card');

// ── Label maps (mirrors escalations.py) ────────────────────────────────────────

const ACTION_LABELS = {
  isolate_vm:           'VM isolated from network',
  release_isolation:    'Isolation lifted',
  snapshot:             'Forensic snapshot created',
  block_suspicious_ip:  'Suspicious IP blocked',
  revoke_temp_access:   'Temporary access revoked',
  restore_from_backup:  'Restore from backup',
  delete_resource:      'Resource deleted',
  wipe_storage:         'Storage wiped',
  modify_network_rule:  'Network rule modified',
  escalate_permissions: 'Permissions escalated',
  activate_autonomy:    'Autonomous response held',
  review_isolation:     'Isolation to review (TTL)',
  review_bypass:        'Bypass to review (someone else\'s rule)',
  repair_local_state:   'Local state to repair',
  review_left_rule:     'Rule left to review (it aims at another VM)',
  review_unverified:    'Isolation or block not verified (the check fails)',
  review_drain:         'Session cut pending (Run Command still running on Azure)',
  review_dormant_isolation: 'Possible older isolation to check (nothing taken off)',
};

// Verb forms — used for actions not yet executed (mode_hold: recommended, pending approval)
const ACTION_LABELS_VERB = {
  isolate_vm:          'Isolate VM',
  release_isolation:   'Release isolation',
  snapshot:            'Create forensic snapshot',
  block_suspicious_ip: 'Block suspicious IP',
  revoke_temp_access:  'Revoke temporary access',
};

function actionLabelVerb(action) {
  return ACTION_LABELS_VERB[action] || ACTION_LABELS[action] || action;
}

const ESC_LABELS = {
  low_confidence:      'low confidence',
  destructive_action:  'destructive action',
  proposed_action:     'unknown action',
  verification_failed: 'verification failed',
  proposed_rule:       'proposed rule',
  posture_gap:         'posture gap',
  mode_hold:           'mode human-only',
  write_blocked:       'write blocked',
  action_failed:       'action failed',
  cycle_failed:        'signal not processed',
  uncharacterized_signal: 'uncharacterized signal',
  release_hold:        'release held',
  detection_blocked:   'detection prevented (rule in place)',
  unattributed_signal: 'not attributed to this VM',
  telemetry_gap:       'telemetry incomplete',
  unstable_decision:   'decision unstable (draws disagree)',
  floor_proposal:      'isolation proposed by the floor (brute force, then root), never run alone',
  ceiling_proposal:    'isolation proposed under the rule\'s ceiling (its evidence alone is not enough), never run alone',
  ttl_exceeded:        'TTL exceeded',
  readiness_hold:      'reserves to confirm',
  orphan_rule:         'orphan rule (NIC gone)',
  dormant_isolation:   'possible older Glorfindel isolation (fixed names, never taken off alone)',
  quarantine_altered:  'quarantine NSG altered',
  control_plane_change: 'control plane, detection only',
  identity_change:     'Entra ID, detection only',
  protected_address:   'protected address (never blocked)',
  lateral_source:      'isolation of the source VM proposed (a brute force from the client\'s network), never run alone',
  lateral_unknown_source: 'brute force from the client\'s network, no monitored VM to isolate (to examine)',
  client_network_unreadable: 'client network unreliable (blocks outside the Internet refused)',
  network_changed:     'named network changed (what its name designates)',
  exposed_block_lifted: 'exposed zone block lifted by Glorfindel (24 h, or the address now another VM\'s)',
  exposed_block_lift_failed: 'exposed zone block: its lift failed (tried again every pass)',
  uncontained_detection: 'detection not contained (snapshot only)',
  bypassed:            'bypassed (an allow before our deny)',
  state_unreadable:    'local state unreadable',
  memory_fallback:     'memory by keys not opened (the watch falls back on the distance)',
  rule_left:           'block rule left (turned, it aims at another VM)',
  unverified:          'not verified (the check fails)',
  account_compromised: 'account maybe compromised (brute force, then a login)',
  compromise_unchecked: 'login after a brute force not checked',
  queue_tampered:      'action queue: a request its service did not write',
  queue_unavailable:   'action queue: the watch\'s register unreadable',
  undecided_detection: 'not decided by the model (deduplicated, ceiling, queue full, budget)',
  model_budget_tripped: 'model breaker tripped (the day\'s budget, or the provider\'s limit)',
  drain_pending:       'session cut pending (the isolation holds, the cut is followed)',
  autonomous_action:   'taken alone and verified (to judge)',
};

// Cards anchored on a VM the detection does not name (an Activity Log row, an identity,
// an unattributed detection — glorfindel/bot.py _ANCHORED_TYPES): no button nor command
// aimed at that VM. Detection only (AL1, C2): decided by the code, nothing recommended.
// Not decisions: the cards TO JUDGE leaves out (escalations._NOT_DECISIONS).
const _ANCHORED_TYPES = new Set(['control_plane_change', 'identity_change', 'unattributed_signal']);
const _DETECTION_ONLY = new Set(['control_plane_change', 'identity_change']);
// RTT1 (#1174; Jonathan 25/11, on a mockup): a detection-only card is titled by its rule — `rule_title`,
// written by the rule alone (RTT1a), carried on the card, read again as the Python reads it
// (Console.ruleTitle, console.js). Unreadable or absent (a card from before), the family's neutral title.
// Never from the signal nor the model; the type and its guards do not change.
function _ruleTitle(e) { return Console.ruleTitle(e); }
const _NOT_DECISIONS = new Set(['posture_gap', 'orphan_rule', 'quarantine_altered', 'proposed_rule',
  'readiness_hold', 'ttl_exceeded', 'detection_blocked', 'bypassed', 'state_unreadable', 'rule_left',
  'unverified', 'queue_tampered', 'queue_unavailable', 'drain_pending',
  'client_network_unreadable', 'network_changed', 'exposed_block_lifted', 'exposed_block_lift_failed',
  'dormant_isolation', 'model_budget_tripped', 'memory_fallback']);
function _isAnchored(e) { return _ANCHORED_TYPES.has(e.escalation_type); }
// A card on an NSG (a quarantine altered, an orphan rule no VM holds) gets an NSG tile.
function _isNsgId(rid) { return /\/providers\/microsoft\.network\/networksecuritygroups\//i.test(rid || ''); }
// A card about Glorfindel's local state (SEC4b: `~/.glorfindel`, no cloud resource) gets
// no tile: it was a phantom VM, counted among the unprotected ones. It stays in the feed.
function _isLocalState(rid) { return /^~\//.test(rid || ''); }

// An autonomous action a gate held back: recommended, NOT executed. It used to read
// "VM isolated from network" as if done, with only an Ack (third review, T14). Say it
// is held, and why, with the one-click approve path every held type deserves.
// Not unattributed_signal: its card is anchored on a VM the detection did not name, and
// the server refuses to execute it (fourth review, Q4).
const _HELD_TYPES = new Set(['mode_hold', 'low_confidence', 'uncharacterized_signal', 'release_hold', 'telemetry_gap', 'unstable_decision', 'floor_proposal', 'ceiling_proposal', 'lateral_source']);
const _APPROVABLE = new Set(['isolate_vm', 'block_suspicious_ip', 'release_isolation', 'snapshot']);
// ATT1 (#936): the actions aimed at the card's VM (eregion_core/action_queue.py VM_AIMED_ACTIONS).
// On a card that says it is unattributed, whatever its type, never an « Approve & execute »: the VM
// is the one the card is filed on, not one the detection names — the server refuses it too.
// SEC-Ed (#954): the snapshot too — the human chooses the VM to snapshot, whatever the card's type.
const _VM_AIMED = new Set(['isolate_vm', 'block_suspicious_ip', 'release_isolation', 'revoke_temp_access', 'snapshot']);
function _aimsLoose(e) { return !!_unattributed(e) && _VM_AIMED.has(e.action); }
function _isHeld(e) {
  return _HELD_TYPES.has(e.escalation_type) && _APPROVABLE.has(e.action)
    && !(e.action === 'snapshot' && e.escalation_type === 'low_confidence')
    && !_aimsLoose(e);
}
// A held snapshot to take by hand (« 📸 Snapshot ») — never on an unattributed card (ATT1): it would
// snapshot the VM the card is filed on, which the detection does not name.
function _looseSnapshot(e) { return e.action === 'snapshot' && !!_unattributed(e); }
// SEC-Ed (#954): what such a card says — the human chooses the VM (a constant, nothing from outside).
const _LOOSE_SNAPSHOT_SAID = 'the detection names no VM: choose the VM to snapshot';
function _isSnapshotPending(e) {
  return e.action === 'snapshot' && e.escalation_type === 'low_confidence' && !_unattributed(e);
}
// JUG1 (#760): a disruptive action Glorfindel took alone, its check held — done, to judge after
// the fact. Nothing to approve on it: it is undone, if judged wrong, by the usual paths.
function _isExecuted(e) { return e.escalation_type === 'autonomous_action'; }

// LEG1 (#1181; Jonathan 25/11, on a mockup): a line from a module says an action by its colour, and
// where it stands by its stroke — dotted and flowing toward the tile while a human must act, solid once
// done. An action Glorfindel took alone draws no dotted line: nothing to approve, only its verdict
// waits. One table for what the map draws and what its legend says: a mark drawn is a mark said.
const _ACTION_MARKS = [
  { key: 'isolate', color: 'var(--red)',    wait: 'isolate · check failed',             done: 'isolated' },
  { key: 'block',   color: 'var(--orange)', wait: 'block',                              done: 'blocked' },
  { key: 'restore', color: 'var(--green)',  wait: 'restore',                            done: 'restoring' },
  { key: 'detect',  color: 'var(--blue)',   wait: 'detection to judge · rule proposed', done: '' },
  { key: 'other',   color: 'var(--purple)', wait: 'other card',                         done: '' },
];
function _mark(key) { return _ACTION_MARKS.find(m => m.key === key); }
// Where a line arrives on its tile (LEG1, the relecture), in the order of the modules it comes from — DETECT
// on the left, PROTECT in the middle, RECOVER on the right — so that no line crosses another before it
// arrives, and none lies over another: DETECT waiting −30; PROTECT's states done −6, 0, +6, then isolate +14,
// block +22, another card +30; RECOVER's restore in course +38, waiting +46.
const _RESTORING_DX = 38;
const _WAIT_DX = { detect: -30, isolate: 14, block: 22, other: 30, restore: 46 };
function _waitDx(key) { return Object.hasOwn(_WAIT_DX, key) ? _WAIT_DX[key] : 30; }
// What a card waiting for a human asks, and from which module; null for an action taken alone.
function _cardEdge(e) {
  if (_isExecuted(e)) return null;
  const key = e.action === 'restore_from_backup' ? 'restore'
    : (e.action === 'isolate_vm' || e.escalation_type === 'verification_failed') ? 'isolate'
    : e.action === 'block_suspicious_ip' ? 'block'
    : (e.action === 'improve_detection' || _DETECTION_ONLY.has(e.escalation_type)) ? 'detect'
    : 'other';
  return { key, color: _mark(key).color, from: key === 'restore' ? 'recover' : key === 'detect' ? 'detect' : 'protect' };
}
// The legend under the map: five lines, read from _ACTION_MARKS and the tiles' own marks (LEG1).
function _legend() {
  const ln = (color, cls = '', width = 2.5, op = 1) =>
    `<svg class="lg-ln" viewBox="0 0 26 8" aria-hidden="true"><path d="M0 4 H26" stroke="${color}" stroke-width="${width}" opacity="${op}"${cls ? ` class="${cls}"` : ''}/></svg>`;
  const sw = (mark, label) => `<span class="lg-sw">${mark}${label}</span>`;
  const dot = (color, label, cls = '') => sw(`<span class="${cls}" style="color:${color}">●</span>`, label);
  const box = (color, cls, label) => sw(`<span class="lg-box ${cls}" style="color:${color}"></span>`, label);
  return `<div class="legend">
        <div class="lg-row lg-lines"><span class="lg-h">MODULES</span>${sw(ln('var(--blue)', '', 1.5, 0.45), 'detect')}${sw(ln('var(--orange)', '', 1.5, 0.45), 'protect')}${sw(ln('var(--green)', '', 1.5, 0.45), 'recover')}</div>
        <div class="lg-row lg-lines"><span class="lg-h">WAITING</span>${_ACTION_MARKS.map(m => sw(ln(m.color, 'edge-wait'), m.wait)).join('')}</div>
        <div class="lg-row lg-lines"><span class="lg-h">DONE</span>${_ACTION_MARKS.filter(m => m.done).map(m => sw(ln(m.color), m.done)).join('')}</div>
        <div class="lg-row"><span class="lg-h">DOTS</span>${dot('var(--green)', 'clean')}${dot('var(--purple)', 'a card waits')}${dot('var(--blue)', 'a verdict waits')}${dot('var(--red)', 'isolated')}${dot('var(--orange)', 'blocked')}${dot('var(--green)', 'restoring', 'dot-pulse')}</div>
        <div class="lg-row"><span class="lg-h">TILES</span>${dot('var(--dim)', 'unverifiable · maybe off · logs silent')}${dot('var(--red)', 'a rule in error (Entra ID, control plane)')}${box('var(--green)', 'dot-pulse', 'restoring')}${box('var(--orange)', 'dot-pulse', 'lifting')}${box('var(--dim)', 'lg-dash', 'excluded')}</div>
      </div>`;
}
function _heldWord(e) {
  return e.escalation_type === 'mode_hold' ? 'pending approval' : 'held: ' + escLabel(e.escalation_type);
}

function actionLabel(action) {
  return ACTION_LABELS[action] || action;
}

function escLabel(type) {
  return ESC_LABELS[type] || type;
}

// Readable titles for escalation types that are NOT tied to a real remediation action
// (the card would otherwise show the raw type, e.g. "posture_gap").
const _ESC_TITLES = {
  posture_gap:    'Posture gap',
  orphan_rule:    'Orphan Glorfindel rule',
  dormant_isolation:    'Possible older Glorfindel isolation — said, never taken off',
  proposed_rule:  'Detection rule proposed',
  ttl_exceeded:   'Isolation TTL exceeded',
  proposed_action:'Unknown action proposed',
  cycle_failed:   'Signal not processed — triage by hand',
  quarantine_altered:   'Quarantine NSG altered',
  bypassed:             'Isolation or block bypassed',
  state_unreadable:     'Local state unreadable',
  rule_left:            'Block rule left as it was',
  unverified:           'Isolation or block not verified',
  drain_pending:        'Session cut pending — followed on Azure (DRN1)',
  control_plane_change: 'Control-plane detection',   // RTT1: the neutral title, a rule's own before it
  identity_change:      'Entra ID detection',
  model_budget_tripped: 'Model breaker tripped',
  account_compromised:  'Account maybe compromised — always to a human (COR1)',
  compromise_unchecked: 'Login after a brute force not checked (COR1)',
  undecided_detection:  'Detection not decided by the model — triage by hand',
};

// What a card is about, on one line: technique, confidence, severity (critical stands
// out), type. A detection-only card also names its rule: it recommends nothing.
function _escCtx(e, pct, lean, title, manyRules) {
  const sev = e.severity === 'critical' ? '<b style="color:var(--red)">critical</b>' : _attr(e.severity || '');
  // A group of several rules (manyRules) never names its first card's rule for all.
  const rule = _DETECTION_ONLY.has(e.escalation_type) && e.rule_name && !manyRules ? 'rule ' + _attr(e.rule_name) : '';
  const ttp = _attr(e.ttp || '');
  return (lean ? [ttp, sev] : [ttp, pct, sev, rule, _attr(_escSaid(e, title))])
    .filter(Boolean).join(' · ');
}
// RTT1: what a detection-only card is, said by its rule's title; else its type. `title`, a group's: the
// rule's title its cards share, '' when they share none — the type then, never one card's for all.
function _escSaid(e, title) {
  const t = _DETECTION_ONLY.has(e.escalation_type) && (title === undefined ? _ruleTitle(e) : title);
  // The neutral title (RTT1a writes it for a rule without one) says no more than the type's own words.
  return t && t !== _ESC_TITLES[e.escalation_type] ? `${t} (detection only)` : escLabel(e.escalation_type);
}
// What the command said when a restore of this card was refused or failed (SEC4c): on the
// card, never silence.
function _restoreFailure(e) {
  const f = (_state?.restore_failures || {})[e.id];
  if (!f) return '';
  return `<div class="esc-context" style="color:var(--red)" title="${_attr(f.at)}">✗ Restore refused or failed: ${_attr(f.error)}</div>`;
}
// AL1c (#597): what a card of the control plane or of an identity is about — its `target`, read
// by the watch in the row (glorfindel/card_target.py): an NSG and the VMs it covers, a disk's VM,
// a role's scope, the group, the control plane as a whole, an identity. A card from before AL1c
// has none: it stays on the VM it was anchored on, and says so.
const _TARGET_KINDS = { vm: 'VM', nsg: 'NSG', resource_group: 'resource group',
  control_plane: 'the control plane', identity: 'identity' };
function _targetOf(e) {
  const t = e && e.target;
  return (t && typeof t === 'object' && Object.prototype.hasOwnProperty.call(_TARGET_KINDS, t.kind)) ? t : null;
}
// Every identity card on one tile, never a VM's (the bot's one thread, the same way).
// A tile of its own — the identities', a group's, the control plane's — is named with a « : »,
// which no VM's name holds: never one tile with a VM of the same name (review, AL1c).
const _IDENTITY_TILE = 'entra:identities';
function _isIdentityCard(e) { const t = _targetOf(e); return !!t && t.kind === 'identity'; }
// IDT1 (#1182; Jonathan 25/11, on a mockup): Entra ID and the control plane on the map as a VM is — always
// there while their rules run (a rule of their source, enabled and bound to a backend), not only when a
// card calls them. Their health by their dot: green, their rules poll (and their logs come, LOGF1); grey,
// no log for `silent_after_hours` (the watch's, never a threshold of the page's); red, a poll in error.
// The tables are the ones their logs land in: a table the watch does not report is not guessed.
const _WATCHED = {
  identity:      { tile: 'entra:identities', label: 'Entra ID — identities', source: 'azure_entra',
                   tables: ['AuditLogs', 'AADServicePrincipalSignInLogs'], resource_id: 'entra:identities',
                   setting: "the tenant's diagnostic setting (AuditLogs, ServicePrincipalSignInLogs)" },
  control_plane: { tile: 'plane:control', label: 'the control plane', source: 'azure_activity',
                   tables: ['AzureActivity'], resource_id: 'control-plane',
                   setting: "the subscription's diagnostic setting (Administrative)" },
};
function _watchedRules(kind) {
  const w = _WATCHED[kind];
  return w ? (_cfgData?.detection?.rules || []).filter(r => r.source === w.source && r.enabled !== false) : [];
}
const _LOGS_READ_STALE_MS = 2 * 15 * 60e3;   // IDT1: twice LOGF1's reading period
function _isWatched(kind) { return _watchedRules(kind).some(r => r.monitoring_backend_name); }
function _ageSaid(iso) { return iso ? _relTime(iso) : ''; }
// What the tile says of itself: { state: ok | silent | error, said, logs: [{name, last, error}] | null }.
function _watchedHealth(kind) {
  const w = _WATCHED[kind];
  const bound = _watchedRules(kind).filter(r => r.monitoring_backend_name);
  const failing = bound.find(r => r.last_error);
  if (failing) return { state: 'error', short: `rule ${failing.name} in error`, said: `rule ${failing.name} in error: ${String(failing.last_error).slice(0, 160)}`, logs: null };
  const lf = Console.watchStatus()?.log_freshness;
  // A watch before LOGF1: its rules poll, its logs not read — green, never grey.
  if (!lf || typeof lf !== 'object' || !lf.tables || typeof lf.tables !== 'object') return { state: 'ok', said: '', logs: null };
  // A read that hangs: `read_at` stops moving — what it said is no longer known, never kept green.
  // Twice the watch's reading period (LOGF1: every 15 min).
  const readAt = Date.parse(lf.read_at || '');
  if (Number.isFinite(readAt) && Date.now() - readAt > _LOGS_READ_STALE_MS)
    return { state: 'silent', short: 'its logs not read for 30 min', said: `its logs' freshness not read since ${_relTime(lf.read_at)}: the watch's read hangs?`, logs: null };
  const logs = w.tables.filter(t => Object.hasOwn(lf.tables, t))
    .map(t => ({ name: t, last: (lf.tables[t] || {}).last || null, error: (lf.tables[t] || {}).error || null }));
  if (!logs.length) return { state: 'ok', said: '', logs };
  if (logs.every(l => l.error)) return { state: 'error', short: 'its logs not read', said: `logs not read: ${String(logs[0].error).slice(0, 160)}`, logs };
  const hours = Number(lf.silent_after_hours);
  const newest = logs.map(l => Date.parse(l.last || '')).filter(Number.isFinite).sort((a, b) => b - a)[0];
  // `last: null` without error: read, and no log in the window — silent too; an error is never « no log ».
  const silent = hours > 0 && (newest === undefined || Date.now() - newest > hours * 3600e3);
  return silent ? { state: 'silent', short: `no log for ${hours} h or more`, said: `no log for ${hours} h or more — ${w.setting}?`, logs } : { state: 'ok', said: '', logs };
}
// The folded line of a watched tile: its rules, its last match, its logs' age — or what is wrong.
function _watchedLine(kind, health) {
  // Short on the folded tile, whole on its hover and in its unfolded block.
  if (health.state !== 'ok') return `<span style="font-size:9px;color:${health.state === 'error' ? 'var(--red)' : 'var(--yellow)'}" title="${_attr(health.said)}">${health.state === 'error' ? '✗' : '⚠'} ${_attr(health.short)}</span>`;
  const rules = _watchedRules(kind);
  const last = rules.map(r => r.last_match || '').filter(Boolean).sort().pop();
  const newest = (health.logs || []).map(l => l.last || '').filter(Boolean).sort().pop();
  return `<span style="font-size:9px;color:var(--dim)">${Number(rules.length)} rule${rules.length === 1 ? '' : 's'}${last ? ` · last match ${_attr(_ageSaid(last))}` : ''}${newest ? ` · logs ${_attr(_ageSaid(newest))}` : ''}</span>`;
}
// Unfolded: as a VM's identity block (VMI1) — where it is read, its logs, its rules, what is set aside.
function _watchedBlock(kind, health) {
  const w = _WATCHED[kind];
  const rules = _watchedRules(kind);
  const az = _cfgData?.azure || {};
  const k = (key, val, cls = '') => val ? `<span class="vm-id-k">${key}</span><span class="${cls}">${val}</span>` : '';
  const ws = [...new Set(rules.map(r => r.monitoring_backend_name).filter(Boolean))].map(x => _attr(x)).join(', ');
  const logs = health.logs === null ? k('logs', 'not read by this watch (before LOGF1)', 'dim')
    : (health.logs || []).map(l => k(_attr(l.name), l.error ? `✗ ${_attr(String(l.error).slice(0, 120))}`
        : l.last ? _attr(_ageSaid(l.last)) : 'none in the window read', l.error ? 'bad' : l.last ? '' : 'warn')).join('');
  const rows = rules.map(r => k(_attr(r.name), r.last_error ? `✗ ${_attr(String(r.last_error).slice(0, 120))}`
      : !r.monitoring_backend_name ? 'bound to no backend'
      : `polling${r.last_match ? ` · last match ${_attr(_ageSaid(r.last_match))}` : ' · never matched'}`,
    r.last_error ? 'bad' : !r.monitoring_backend_name ? 'warn' : '')).join('');
  const msi = rules.reduce((n, r) => n + (Number(r.msi_certificate_count) || 0), 0);
  return `<div class="vm-id watched">
      ${health.state !== 'ok' ? `<span class="vm-id-h ${health.state === 'error' ? 'bad' : 'warn'}">${_attr(health.said)}</span>` : ''}
      ${kind === 'identity' ? k('tenant', _attr(az.tenant_id || '')) : k('subscription', _attr(az.subscription_id || ''))}
      ${k('workspace', ws)}
      <span class="vm-id-h">LOGS</span>${logs}
      <span class="vm-id-h">RULES</span>${rows}
      ${kind === 'identity' && msi ? `<span class="vm-id-h">SET ASIDE</span>${k('MSI certificates', `${Number(msi)} (Azure's own, MID1)`, 'dim')}` : ''}
    </div>`;
}
function _isIdentityId(rid) { return /^entra:/.test(rid || ''); }
// The tile of its own a card is filed on (its name), or '' for a VM's or an NSG's.
function _ownTile(e) {
  const t = _targetOf(e);
  if (!t) return '';
  if (t.kind === 'identity') return _IDENTITY_TILE;
  if (t.kind === 'resource_group') return 'group:' + String(e.resource_id || '').toLowerCase();
  if (t.kind === 'control_plane') return 'plane:control';
  return '';
}
// RTT1b: what a title names for a card on a tile of its own — the tile's label (« Entra ID — identities »,
// « the control plane »), never its key (`entra:identities`, `plane:control`), as showEscModal does.
function _tileSaid(e) {
  const own = _ownTile(e);
  return own ? ((_tiles.get(own) || {}).label || own) : '';
}
// The cards a tile shows: its own; on the identities' tile, every identity card; on a VM's, the
// cards about an NSG that covers it too. A card on a tile of its own is on that tile only —
// never matched by the last segment of its id.
function _onTile(e, r) {
  if (r.kind === 'identity') return _isIdentityCard(e);
  if (_isIdentityCard(e)) return false;
  const own = _ownTile(e);
  if (own || r.kind) return own === r.vm_name;
  return e.resource_id === r.resource_id || e.resource_id.split('/').pop() === r.vm_name
    || (!r.is_nsg && !r.is_cluster && _coversVm(e, r.resource_id));
}
let _tiles = new Map();   // vm_name → the tile rendered (renderInfra): what a modal of it shows
// A card about an NSG is shown on each VM it covers, the same card (one Ack).
function _coversVm(e, rid) {
  const t = _targetOf(e);
  const id = String(rid || '').toLowerCase();
  return !!t && t.kind === 'nsg' && Array.isArray(t.vms) && !!id
    && t.vms.some(v => String(v).toLowerCase() === id);
}
const _VMS_SHOWN = 8;
function _targetNote(e, vmName) {
  const t = _targetOf(e);
  if (t) {
    const named = t.kind === 'control_plane' ? '' : ' ' + _attr(t.name || '?');
    const kind = t.kind === 'identity' ? _attr(t.identity_type || 'identity') : _TARGET_KINDS[t.kind];
    const via = t.via ? ` · ${_attr(t.via)}` : '';
    // The VMs an NSG covers: named up to _VMS_SHOWN, the rest counted (the bot's way).
    const vms = Array.isArray(t.vm_names) ? t.vm_names : [];
    const more = vms.length > _VMS_SHOWN ? ` and ${vms.length - _VMS_SHOWN} more` : '';
    const covers = vms.length
      ? ` · covers ${vms.slice(0, _VMS_SHOWN).map(v => _attr(v)).join(', ')}${more}` : '';
    const limit = t.limit
      ? `<div class="esc-context" style="color:var(--dim)" title="What the row, and Azure, could not say">limit: ${_attr(t.limit)}</div>` : '';
    return `<div class="esc-context" title="What the detection is about, read in its row">🎯 about ${kind}${named}${via}${covers}</div>${limit}`;
  }
  // SLF1 (#929): a detection attributed to no VM — « not attributed », its candidates; never the
  // name of the VM it is filed on.
  const loose = _unattributed(e);
  if (loose) {
    const choose = _looseSnapshot(e) ? ` · ${_attr(_LOOSE_SNAPSHOT_SAID)}` : '';
    return `<div class="esc-context" title="${_attr(_LOOSE_TITLE)}">⚓ ${_attr(_unattributedTxt(loose))}${choose}</div>`;
  }
  if (!_isAnchored(e) || e.escalation_type === 'unattributed_signal') return '';
  // Filed before AL1c: on the first VM online, or on the VM itself (a role on the VM, a signal of
  // `respond`) — the card cannot tell which.
  return `<div class="esc-context" title="${_attr(_FILED_BEFORE)}">⚓ filed on ${_attr(vmName)}, may not be about it</div>`;
}
const _FILED_BEFORE = 'Filed before AL1c, without its target: the detection may not be about this VM';
// SLF1 (#929): what a card on a detection attributed to no VM says in place of its resource
// (glorfindel/escalations.py `unattributed`): its candidates, or the appliance it came through. A
// card recorded so (`attribution`), or held by the attribution guard (its candidates not kept);
// never a card filed on its target (AL1c).
const _LOOSE_TITLE = 'The detection names no VM, and no watched VM made the call: the card is only filed on this tile. Check which VM it is about before acting.';
function _unattributed(e) {
  if (!e || _targetOf(e)) return null;
  const a = e.attribution;
  if (a && typeof a === 'object' && a.state === 'unattributed') {
    return { candidates: Array.isArray(a.candidates) ? a.candidates.filter(c => typeof c === 'string') : [],
             appliance: typeof a.appliance === 'string' ? a.appliance : '' };
  }
  return e.escalation_type === 'unattributed_signal' ? { candidates: [], appliance: '' } : null;
}
function _unattributedTxt(u) {
  if (u.appliance) return `not attributed — the call came from ${u.appliance}, which forwards packets: the source VM is behind it`;
  if (!u.candidates.length) return 'not attributed — the detection names no VM';
  const more = u.candidates.length > _VMS_SHOWN ? ` and ${u.candidates.length - _VMS_SHOWN} more` : '';
  return `not attributed — candidates: ${u.candidates.slice(0, _VMS_SHOWN).join(', ')}${more}`;
}
// ATT1 (#936): a card on a detection attributed to no VM holds an action nothing ran — never its
// past label (« VM isolated from network »): its verb, held, not attributed. Not a card whose action
// did run (taken alone, a failed check, a write refused or failed).
const _RAN_TYPES = new Set(['autonomous_action', 'verification_failed', 'write_blocked', 'action_failed']);
function _looseTitle(e) {
  if (!_unattributed(e) || !ACTION_LABELS_VERB[e.action] || _RAN_TYPES.has(e.escalation_type)) return '';
  return `${ACTION_LABELS_VERB[e.action]} — held: not attributed`;
}
function escTitle(e) {
  const loose = _looseTitle(e);
  if (loose) return loose;
  if (_DETECTION_ONLY.has(e.escalation_type)) return _ruleTitle(e) || _ESC_TITLES[e.escalation_type];   // RTT1
  // Real remediation action → its label; otherwise a readable type title.
  if (e.action && ACTION_LABELS[e.action]) return ACTION_LABELS[e.action];
  return _ESC_TITLES[e.escalation_type] || escLabel(e.escalation_type) || e.action || '?';
}

// RTT1: a group (_groupEscs) folds the cards of one action — detection-only cards of several rules fold
// together. Titled by its rule when all its cards share that title; else the family's neutral title, with
// how many rules.
function _sharedRuleTitle(group) {
  const titles = new Set(group.map(x => _ruleTitle(x)));
  return titles.size === 1 ? [...titles][0] : '';
}
function _sharedTitle(group) {
  const e = group[0];
  if (!_DETECTION_ONLY.has(e.escalation_type)) return escTitle(e);
  const shared = _sharedRuleTitle(group);
  if (shared) return shared;
  const rules = _groupRules(group).size;
  return `${_ESC_TITLES[e.escalation_type] || escLabel(e.escalation_type)}${rules > 1 ? ` · ${rules} rules` : ''}`;
}
// The rules a group's detection-only cards come from — a card of another type, or without a rule, counts none.
function _groupRules(group) {
  return new Set(group.filter(x => _DETECTION_ONLY.has(x.escalation_type)).map(x => x.rule_name || _ruleTitle(x)).filter(Boolean));
}

// NSG scope chip for a block/isolation — makes "VM NSG vs subnet NSG" explicit.
// VM NSG (NIC) = rule on the VM's own NSG, affects this VM only (neutral).
// subnet NSG = rule on the SHARED subnet NSG; new rules are scoped to this VM's IP
// (safe), but a legacy any-rule would hit the whole subnet → faint amber border as a
// "shared resource, be aware" cue (not an alarm — the common scoped case is safe).
// A real blast-radius ⚠ is reserved for when the backend flags a rule as unscoped.
function _scopeNote(s) {
  if (!s || !s.nsg_scope) return '';
  return _scopeChip(s) + _healthNote(s) + _freshNote(s);
}

// When Glorfindel last re-read Azure and found the isolation / block in place (the watch
// re-checks every minute). Older than 5 min = its knowledge of the real state is stale.
function _freshNote(s) {
  if (!s || !s.verified_at) return '';
  const stale = (Date.now() - new Date(s.verified_at).getTime()) > 5 * 60 * 1000;
  const color = stale ? 'var(--orange)' : 'var(--dim)';
  const title = stale
    ? 'Not re-verified for more than 5 minutes — is the watch running? The real state on Azure may differ.'
    : 'Last time Glorfindel re-read Azure and found it in place (checked every minute).';
  return ` <span style="font-size:8px;color:${color};flex-shrink:0" title="${title}">✓ ${age(s.verified_at)}</span>`;
}

function _scopeChip(s) {
  const base = 'font-size:8px;font-weight:600;padding:0 4px;border-radius:3px;color:var(--dim);flex-shrink:0';
  if (s.nsg_scope === 'quarantine')
    return ` <span style="${base};border:1px solid var(--border)" title="Glorfindel's quarantine NSG attached to the NIC (it had no NSG of its own). No customer rule touched; detached on release.">quarantine NSG</span>`;
  if (s.nsg_scope === 'subnet') {
    if (s.blast_radius || s.scoped === false)
      return ` <span style="${base};color:var(--orange);background:color-mix(in srgb,var(--orange) 12%,transparent);border:1px solid color-mix(in srgb,var(--orange) 40%,transparent)" title="Rule on the shared subnet NSG and NOT scoped to this VM — affects the WHOLE subnet.">⚠ subnet-wide</span>`;
    return ` <span style="${base};border:1px solid color-mix(in srgb,var(--orange) 28%,var(--border))" title="Rule on the shared SUBNET NSG, scoped to this VM's IP. The NSG is shared with other subnet VMs; a legacy any-rule here would cover the whole subnet.">subnet NSG</span>`;
  }
  if (s.shared)
    return ` <span style="${base};border:1px solid color-mix(in srgb,var(--orange) 28%,var(--border))" title="NIC-level NSG shared with other NICs (other VMs or a subnet): the rule is scoped to this VM's IP so the other VMs are untouched.">shared NSG</span>`;
  return ` <span style="${base};border:1px solid var(--border)" title="Rule on the VM's own NIC NSG — affects this VM only.">VM NSG</span>`;
}

// Health chips that must never hide behind a plain ISOLATED / BLOCKED badge:
//   partial  — some NICs only, or a release/unblock that left rules in place
//   bypassed — an ALLOW rule is evaluated before our deny (its traffic still passes)
function _healthNote(s) {
  const base = 'font-size:8px;font-weight:700;padding:0 4px;border-radius:3px;flex-shrink:0;color:var(--red);border:1px solid color-mix(in srgb,var(--red) 45%,transparent);background:color-mix(in srgb,var(--red) 10%,transparent)';
  let out = '';
  const leftovers = [...(s.release_failed || []), ...(s.unblock_failed || [])];
  if (s.partial || leftovers.length) {
    const why = leftovers.length
      ? 'Rules could not be removed:\n' + leftovers.join('\n')
      : `Placed on some NICs only — failed on ${s.failed_nic || 'a NIC'}. The placed rules are recorded; Reset removes them.`;
    out += ` <span style="${base}" title="${_attr(why)}">⚠ partial</span>`;
  }
  if (Array.isArray(s.shadowed) && s.shadowed.length) {
    const why = 'ALLOW rule(s) evaluated BEFORE the Glorfindel deny — their traffic still passes:\n'
      + s.shadowed.map(x => `${x.rule} (priority ${x.priority}, ${x.direction}, ports ${x.ports})`).join('\n');
    out += ` <span style="${base}" title="${_attr(why)}">⚠ bypassed</span>`;
  }
  // Isolated by rules (the quarantine NSG was refused or is off): a known limit, not a
  // failure — orange. Azure only lets a rule deny its DNS and IMDS for every NIC behind an
  // NSG, so they stay reachable from this VM (measured; sixth review, S7).
  if (Array.isArray(s.platform_open) && s.platform_open.length) {
    const warn = 'font-size:8px;font-weight:700;padding:0 4px;border-radius:3px;flex-shrink:0;color:var(--orange);border:1px solid color-mix(in srgb,var(--orange) 45%,transparent);background:color-mix(in srgb,var(--orange) 10%,transparent)';
    const why = 'Isolated by rules, not the quarantine NSG, on ' + s.platform_open.join(', ')
      + ':\nAzure DNS and IMDS stay reachable (a rule can only deny them for every NIC behind an NSG).'
      + '\nA DNS tunnel or a managed-identity token remains possible. The quarantine NSG closes both.';
    out += ` <span style="${warn}" title="${_attr(why)}">⚠ DNS/IMDS</span>`;
  }
  // In our quarantine, its original NSG unknown (SEC4b): the release, autonomous too,
  // stops until the operator sets our tag — said on the card now, not first at the release.
  if (Array.isArray(s.original_unknown) && s.original_unknown.length) {
    const warn = 'font-size:8px;font-weight:700;padding:0 4px;border-radius:3px;flex-shrink:0;color:var(--orange);border:1px solid color-mix(in srgb,var(--orange) 45%,transparent);background:color-mix(in srgb,var(--orange) 10%,transparent)';
    const why = 'Original NSG unknown for ' + s.original_unknown.join(', ')
      + ':\nthe release will ask for the tag glorfindel-orig-<hash> on the quarantine NSG'
      + ' (=<NSG id>, or =none).';
    out += ` <span style="${warn}" title="${_attr(why)}">⚠ original unknown</span>`;
  }
  return out + _drainNote(s);
}

// DRN2 (#754): the session cut, as the isolation card says it — pending while it runs on Azure,
// then its outcome, what it says in the title (from the isolation's state alone, DRN2 review). Every
// word from the watch goes through _attr.
const _DRAIN_CHIP = {
  pending: ['var(--orange)', 'cut pending'],
  drained: ['var(--dim)', 'sessions cut'],
  refused: ['var(--red)', '⚠ cut refused'],
  open: ['var(--red)', '⚠ sessions open'],
  never: ['var(--orange)', '⚠ cut never ended'],
};
function _drainNote(s) {
  const d = s && s.drain_view;
  const chip = d && _DRAIN_CHIP[d.case];
  if (!chip) return '';
  const n = Number(d.after_s);
  const after = d.after_s != null && Number.isFinite(n) ? ` · ${n} s` : '';
  const why = d.case === 'pending'
    ? 'Session cut (Run Command) still running on Azure: the isolation holds on the NSG; the cut is read again at each pass of the reassertion, and its outcome said once.'
    : String(d.said || '') + (d.ended_at ? '\nRead ' + String(d.ended_at) : '');
  return ` <span style="font-size:8px;font-weight:600;padding:0 4px;border-radius:3px;flex-shrink:0;color:${chip[0]};border:1px solid color-mix(in srgb,${chip[0]} 40%,transparent)" title="${_attr(why)}">${chip[1]}${after}</span>`;
}

// LEV2 (#690): who acted on the VM by the control plane, and whether they keep their rights —
// read by the watch, FOR INFORMATION only (the lift does not read it yet). Every text from Azure
// goes through _attr; the chip's words are the page's own.
const _DOOR_CHIP = {
  none: { color: 'var(--dim)', label: 'no actor seen' },
  seen: { color: 'var(--orange)', label: 'actors seen' },
  unreadable: { color: 'var(--orange)', label: 'actors unreadable' },
};
function _doorNote(s) {
  const d = s && s.door;
  if (!d) return '';
  const chip = _DOOR_CHIP[d.verdict] || _DOOR_CHIP.unreadable;
  const n = Array.isArray(d.actors) ? Number(d.actors.length) : 0;
  const lines = ['For information: the lift does not read these facts yet.',
    'Read ' + (d.read_at || '?') + ', since ' + (d.since || '?') + '.'];
  for (const w of d.unreadable || []) lines.push('Unreadable: ' + w);
  for (const a of d.actors || []) {
    lines.push((a.role ? a.role + ' ' : '') + (a.ids || []).join(', ') + ' — rights ' + (a.rights || '?'));
    for (const g of a.gestures || []) lines.push('  ' + g.at + ' ' + g.operation + ' (' + g.kind + ', ' + g.status + ')');
    for (const h of a.held || []) lines.push('  held: ' + h);
    for (const w of a.why || []) lines.push('  ' + w);
  }
  if (Array.isArray(s.disks_at_isolation) && s.disks_at_isolation.length)
    lines.push('Disks at the isolation (evidence, never deleted): ' + s.disks_at_isolation.join(', '));
  const base = 'font-size:8px;font-weight:600;padding:0 4px;border-radius:3px;flex-shrink:0;border:1px solid var(--border)';
  return ` <span style="${base};color:${chip.color}" title="${_attr(lines.join('\n'))}">⚑ ${chip.label}${n ? ' · ' + n : ''}</span>`;
}

// Last meaningful lines of a CLI run (release / reset print the rules still in place).
function _cliTail(text, n = 4) {
  return (text || '').split('\n').map(l => l.trim()).filter(Boolean).slice(-n).join(' · ');
}

// Multi-NIC coverage chip — a VM can have several NICs, each behind its own NSG.
// isolate_vm/block place one deny per NIC (placements[]); show "N NICs" so the operator
// sees full coverage (a one-NSG badge could read as if only the primary NIC were covered).
// Only shown when >1 NIC; single-NIC keeps the badge clean.
function _nicNote(s, vmName) {
  const n = Array.isArray(s?.placements) ? Number(s.placements.length) : 0;
  if (n <= 1) return '';
  const nsgs = new Set(s.placements.map(p => p.nsg || `${p.nsg_rg}/${p.nsg_name}`)).size;
  const idx = _coverageCache.push({ vmName, type: s.type, ip: s.ip || '', placements: s.placements }) - 1;
  const base = 'font-size:8px;font-weight:600;padding:0 4px;border-radius:3px;flex-shrink:0;cursor:pointer';
  return ` <span style="${base};color:var(--cyan);border:1px solid color-mix(in srgb,var(--cyan) 35%,var(--border))"
    ${_on('click', 'showCoverageModal', idx)}
    title="Click for per-NIC coverage — deny placed on all ${n} NICs (${nsgs} NSG${nsgs>1?'s':''}).">${n} NICs ▸</span>`;
}

// Per-NIC coverage detail for a multi-NIC isolate/block. Lists each placement
// (NIC → NSG · scope · rule) so the operator sees exactly where each deny landed.
function showCoverageModal(idx) {
  const c = _coverageCache[idx];
  if (!c) return;
  const verb = c.type === 'isolated' ? 'Isolation' : c.type === 'nsg' ? 'NSG' : 'Block';
  const rows = (c.placements || []).map((p, i) => {
    const nsg   = (p.nsg || `${p.nsg_rg || ''}/${p.nsg_name || ''}`).split('/').pop();
    // A NIC without NSG, nor on its subnet (`scope: "none"`, `nsg: ""`): said so, never « NIC NSG » (IPS2).
    const scope = p.scope === 'subnet' ? 'subnet NSG (shared)' : p.scope === 'none' ? 'no NSG' : 'NIC NSG (this VM)';
    const scopeCol = p.scope === 'subnet' ? 'var(--orange)' : p.scope === 'none' ? 'var(--red)' : 'var(--dim)';
    const nic   = p.nic_id ? p.nic_id.split('/').pop() : `NIC ${i + 1}`;
    const ips   = Array.isArray(p.ips) && p.ips.length ? p.ips.join(', ') : '';
    const rules = p.rule_in || p.rule_out
      ? [p.rule_in, p.rule_out].filter(Boolean).join(' · ')
      : (p.rule || '');
    return `<div style="padding:6px 0;border-top:1px solid var(--border)">
      <div style="display:flex;gap:8px;align-items:baseline">
        <span style="color:var(--cyan);font-weight:600;font-size:11px;flex:1">${_attr(nic)}</span>
        <span style="color:${scopeCol};font-size:9px">${scope}</span>
      </div>
      <div style="color:var(--dim);font-size:10px;margin-top:2px">🛡 ${_attr(nsg || '—')}${ips ? ` · ${_attr(ips)}` : ''}</div>
      ${rules ? `<div style="color:var(--dim);font-size:9px;margin-top:1px">rule: ${_attr(rules)}</div>` : ''}
    </div>`;
  }).join('');
  document.getElementById('modal-title').textContent =
    `${verb} coverage — ${c.vmName}${c.ip ? ` (${c.ip})` : ''}`;
  const body = document.getElementById('modal-body');
  const subtitle = c.type === 'nsg'
    ? `${Number((c.placements || []).length)} NICs — NSG on each`
    : `${Number((c.placements || []).length)} NICs covered — one deny placement each`;
  body.innerHTML = `<div style="font-size:10px;color:var(--dim);margin-bottom:4px">${subtitle}</div>${rows}`;
  document.getElementById('modal-cmd').style.display = 'none';
  const btn = document.getElementById('modal-confirm');
  btn.textContent = 'Close'; btn.className = 'action'; btn.onclick = closeModal;
  document.getElementById('modal-cancel').style.display = 'none';
  document.getElementById('modal').classList.add('open');
}

// "Extend to subnet" affordance for an existing VM-scoped block (operator decision), on ITS IP:
// never the VM's first block (CON-K). Hidden once the block is already subnet-wide (scoped === false).
function _extendBtn(s, vmName) {
  if (!s || s.scoped === false) return '';
  return `<button class="action" ${_on('click', 'confirmExtendSubnet', vmName, s.ip)} style="font-size:9px;padding:2px 7px;color:var(--orange)" title="Block this IP for every VM on the subnet">⚠ Extend to subnet</button>`;
}

// A VM's blocks, newest first (CON-K). A subnet-wide one lives on the PROTECT card.
function _blocksOf(states) {
  const t = s => new Date(s.since || 0).getTime() || 0;
  return (states || []).filter(s => s.type === 'blocked' && s.scoped !== false).sort((a, b) => t(b) - t(a));
}

function _ageShort(ts) {
  const s = ts ? Math.floor((Date.now() - new Date(ts).getTime()) / 1000) : NaN;
  if (!(s >= 0)) return '?';
  return s < 3600 ? Math.max(1, Math.floor(s / 60)) + 'm' : s < 172800 ? Math.floor(s / 3600) + 'h' : Math.floor(s / 86400) + 'd';
}

// Several blocks: one line says them all, the card keeps its height whatever their number; the
// list, filterable, each with its buttons, is in its window (decision A of 03/11, showBlocks).
// The window finds its VM by its resource id: two VMs of one name never mixed up.
function _blocksSummary(bs, resourceId) {
  const n = Number(bs.length);
  return `<span class="badge blocked" style="font-size:9px;cursor:pointer" ${_on('click', 'showBlocks', resourceId)}
    title="Every block of this VM, newest first">BLOCKED ×${n} IPs · newest ${_ageShort(bs[0].since)} · oldest ${_ageShort(bs[n - 1].since)}</span>`;
}

function _manageBtn(bs, resourceId) {
  return `<button class="action" ${_on('click', 'showBlocks', resourceId)} style="font-size:9px;padding:2px 7px">Manage the ${Number(bs.length)} blocks ▸</button>`;
}

function _blockBadge(s, vmName) {
  return `<span class="badge blocked" style="font-size:9px;cursor:default">BLOCKED ${_attr(s.ip)} · ${age(s.since)}</span>${_scopeNote(s)}${_nicNote(s, vmName)}`;
}

// One block's own buttons: each acts on its IP alone — Unblock takes off that block, the VM's
// other blocks and its isolation stay (it was a reset of them all).
function _blockBtns(s, vmName) {
  return `${_extendBtn(s, vmName)}<button class="action danger" ${_on('click', 'confirmUnblockIp', vmName, s.ip, s.scoped === false, s.nsg || '')} style="font-size:9px;padding:2px 7px" title="Remove the block of this IP only">↩️ Unblock</button>`;
}

// What a command to copy names a VM by: « <groupe>/<nom> » (MSK3b, #787 — glorfindel/vm_command.py,
// the bot's and the CLI's form), never its name alone nor its full id: copied to another terminal, or
// with a VM of that name in another group, the name alone could take that one (`--yes` asks nothing).
// `glorfindel` resolves it on its own host, the group and the name matching, or refuses. Quoted for
// the shell when the group holds one of its characters (Azure allows « ( ) »). Not a VM's own id (an
// extension, a NSG), or no group: « <id: glorfindel list --ids> ».
function _vmArg(rid) {
  const parts = String(rid || '').trim().replace(/\/+$/, '').split('/');
  const low = parts.map(p => p.toLowerCase());
  const i = low.slice(0, -1).indexOf('resourcegroups');
  if (i >= 0 && low.length >= 2 && low[low.length - 2] === 'virtualmachines'
      && i + 1 < parts.length - 1 && parts[i + 1] && parts[parts.length - 1]) {
    const pair = `${parts[i + 1]}/${parts[parts.length - 1]}`;
    return /^[A-Za-z0-9_@%+=:,.\/-]+$/.test(pair) ? pair : `'${pair.replace(/'/g, `'"'"'`)}'`;
  }
  return '<id: glorfindel list --ids>';
}

// RTZ1 (#923): a card's time without its zone is no moment to copy — never guessed, the CLI refuses it.
const _ZONED_TIME = /\d\d:\d\d(:\d\d(\.\d+)?)?(Z|[+-]\d\d(:?\d\d)?)$/;
function _zonedOr(t, otherwise) {
  const text = String(t || '').trim();
  return _ZONED_TIME.test(text) ? text : otherwise;
}

function cliCommand(esc) {
  const rid = esc.resource_id;
  const id  = esc.id.slice(0, 8);
  // Never a command aimed at the anchor VM (AL1): acknowledge, act from what the card says.
  // ATT1 (#936): nor on a card that says it is unattributed, whatever its type — it says so, and its
  // candidates, and sends the judgement to the CLI.
  const loose = _unattributed(esc);
  if (loose) {
    // A name from the store on one line (a newline would start a command of its own).
    const said = _unattributedTxt(loose).replace(/[\u0000-\u001f\u007f]/g, ' ');
    // SEC-Ed (#954): a snapshot there — the human chooses the VM, never the one the card is filed on.
    const choose = _looseSnapshot(esc)
      ? `# ${_LOOSE_SNAPSHOT_SAID}, then glorfindel snapshot <group>/<name> --yes on that one\n` : '';
    return `# ${said}\n# judge which VM it is about from the CLI (glorfindel pending, the detection's row), then act on that VM\n${choose}glorfindel ack ${id}`;
  }
  if (_isAnchored(esc)) return `glorfindel ack ${id}`;
  // RDW1: the gesture the rule's ceiling left to a human (the model's isolation), before the card's
  // own commands — a held snapshot, or the card of the snapshot run alone.
  const ceiling = _ceilingCommand(esc);
  if (_isHeld(esc)) {
    const vm = _vmArg(rid);
    const ip = esc.ip || (esc.action_params && esc.action_params.ip) || '<ip>';
    const actionMap = {
      isolate_vm:          `glorfindel isolate ${vm} --yes`,
      snapshot:            `glorfindel snapshot ${vm} --yes`,
      block_suspicious_ip: `glorfindel block ${ip} ${vm} --yes`,
      release_isolation:   `glorfindel release ${vm} --yes`,
      revoke_temp_access:  `glorfindel ack ${id}  # revoke_temp_access — manual`,
    };
    return ceiling + (actionMap[esc.action] || `glorfindel ack ${id}`) + `\nglorfindel ack ${id}`;
  }
  if (esc.action === 'restore_from_backup') {
    // The moment is asked (SEC4c): the card's first detection — the attack began before it.
    return `# --before: an instant before the attack began (the card's first detection here — go back if it began earlier)\n`
      + `glorfindel restore ${_vmArg(rid)} --yes --before ${_zonedOr(esc.first_seen || esc.timestamp, '<ISO8601>')}\nglorfindel ack ${id}`;
  }
  if (esc.escalation_type === 'readiness_hold') {
    return `# Shows the reserves, then asks you to accept them\nglorfindel activate ${_vmArg(rid)}`;
  }
  if (esc.escalation_type === 'verification_failed') {
    return `glorfindel revert ${_vmArg(rid)} --yes\nglorfindel ack ${id}`;
  }
  if (_isExecuted(esc)) {
    // JUG1: an action taken alone — judged; undone, if judged wrong, by the usual path (the bot's words).
    const vm = _vmArg(rid);
    const ip = (esc.action_params && esc.action_params.ip) || '<ip>';
    const undo = esc.action === 'isolate_vm' ? `glorfindel release ${vm} --yes` : `glorfindel unblock ${ip} ${vm} --yes`;
    return `glorfindel verdict ${id} right|wrong|unsure\n# judged wrong: undo it by the usual path\n${undo}\nglorfindel ack ${id}`;
  }
  // No restore here: a held snapshot never ran — restoring would overwrite the very
  // disk the model wanted preserved (fourth review, Q16).
  return ceiling + `glorfindel ack ${id}`;
}

// ── Utilities ──────────────────────────────────────────────────────────────────

function age(ts) {
  if (!ts) return '';
  const s = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (s < 60)   return s + 's ago';
  if (s < 3600) return Math.floor(s / 60) + 'm ago';
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h + 'h ' + m + 'm ago';
}

function fmtTime(ts) {
  if (!ts) return '';
  return new Date(ts).toISOString().slice(11, 19) + ' UTC';
}

function toast(msg, ms = 3000) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), ms);
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
  document.querySelector('.modal').classList.remove('wide');
  document.getElementById('modal-confirm').style.display = '';  // restore (block-scope modal hides it)
  document.getElementById('modal-confirm').disabled = false;    // the restore's, while it reads
  document.getElementById('modal').dataset.owner = '';           // the restore's window token
}

function openModal(title, body, cmd, confirmLabel, confirmClass, onConfirm) {
  document.getElementById('modal').dataset.owner = '';
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').textContent = body;
  document.getElementById('modal-confirm').style.display = '';
  const cmdEl = document.getElementById('modal-cmd');
  if (cmd) { cmdEl.textContent = cmd; cmdEl.style.display = ''; }
  else cmdEl.style.display = 'none';
  const btn = document.getElementById('modal-confirm');
  btn.textContent = confirmLabel;
  btn.className = confirmClass;
  btn.onclick = () => { closeModal(); onConfirm(); };
  document.getElementById('modal').classList.add('open');
}

function showReasoning(vmName, idx) {
  const cached = _actionsCache[vmName];
  if (!cached) return;
  const a = cached.actions[idx];
  if (!a) return;

  const pct  = a.confidence ? ` · ${Math.round(a.confidence * 100)}%` : '';
  const title = `${actionLabel(a.action)}${pct} — ${a.ttp || ''} — ${a.timestamp ? new Date(a.timestamp).toISOString().slice(11,19) + ' UTC' : ''}`;
  const text  = a.full_reasoning || a.reasoning || '(no reasoning available)';

  document.getElementById('modal-title').textContent = title;
  // Render reasoning with step headers highlighted
  const formatted = text
    .replace(/^(Étape\s+\d+\s*[–\-:].*)/gim, '\n$1\n')
    .replace(/^(Step\s+\d+\s*[–\-:].*)/gim, '\n$1\n')
    .trim();
  const bodyEl = document.getElementById('modal-body');
  bodyEl.textContent = formatted;

  const cmdEl = document.getElementById('modal-cmd');
  cmdEl.style.display = 'none';

  const btn = document.getElementById('modal-confirm');
  btn.textContent = 'Close';
  btn.className = 'action';
  btn.onclick = closeModal;

  document.getElementById('modal').classList.add('open');
}

function openCommandModal(escId) {
  const esc = _escById[escId];
  if (!esc) return;
  const cmd = cliCommand(esc);
  const isSnapshotPending = _isSnapshotPending(esc);
  const isCmdModeHold = _isHeld(esc);
  const label = isCmdModeHold ? actionLabelVerb(esc.action) + ' — ' + _heldWord(esc)
              : isSnapshotPending ? 'Snapshot recommended' : (_looseTitle(esc) || actionLabel(esc.action));
  document.getElementById('modal-title').textContent = '📋 ' + label;
  document.getElementById('modal-body').textContent = 'CLI command to run for this escalation:';
  const cmdEl = document.getElementById('modal-cmd');
  cmdEl.textContent = cmd;
  cmdEl.style.display = '';
  document.getElementById('modal-cancel').style.display = 'none';
  const btn = document.getElementById('modal-confirm');
  btn.textContent = 'Close';
  btn.className = 'action';
  btn.onclick = () => {
    closeModal();
    document.getElementById('modal-cancel').style.display = '';
  };
  document.getElementById('modal').classList.add('open');
}

// ── State ──────────────────────────────────────────────────────────────────────

let _state      = { resources: [], escalations: [] };
let _escById    = {};
let _cfgData    = null;
let _auditData     = null;   // null=never loaded, {audits:[]} = loaded (possibly empty)
let _auditLoading  = false;
let _auditLastRun  = null;   // ISO timestamp of last successful fetch
let _backupItems   = null;   // null=never loaded, {vault, items[], error?} = loaded — vault inventory for RECOVER
let _backupLoading = false;
let _nsgItems      = null;   // null=never loaded, {nsgs[], error?} = loaded — full NSG inventory for PROTECT
let _nsgLoading    = false;
let _auditStale    = null;   // error string when a refresh failed but last-good data is kept
let _backupStale   = null;   // idem for /api/backups — resilience: never wipe cards on a transient timeout
let _nsgStale      = null;   // idem for /api/nsgs
let _actionsCache = {};   // vm_name → {actions, fetchedAt}
let _autoScroll = true;

// ── Infrastructure cards ───────────────────────────────────────────────────────

// A vault item is named 'VM;iaasvmcontainerv2;<rg>;<vm>': the VM is its last segment.
function _backupVmName(it) {
  const raw = it.name || (it.resource_id || '').split('/').pop() || '';
  return raw.split(';').pop();
}

// A rule match is news for half an hour, then history.
function _matchColor(ts) {
  const t = Date.parse(ts);
  return (t && Date.now() - t < 30 * 60 * 1000) ? 'var(--orange)' : 'var(--dim)';
}

// I3G (#446): the cards the reassertion writes — their signal ids, whatever their case, as the
// store tells them (escalations._reassertion). Never grouped with a card of another origin: the
// graph's card and the reassertion's alert on one VM made one group, under the first one's
// title, and one Ack acknowledged both — the alert silenced unread.
const _REASSERTION = ['reassert-', 'state-unreadable-'];
function _fromReassertion(e) {
  const sid = String(e.signal_id || '').toLowerCase();
  return _REASSERTION.some(p => sid.startsWith(p));
}

// DRN1 (#677): the cards of the session cut followed on Azure (escalations._DRAIN_FOLLOW) — an origin
// of their own: never grouped with another card of the reassertion on the VM (one title, one Ack).
const _DRAIN_FOLLOW = 'reassert-drain:';
function _fromDrain(e) {
  return String(e.signal_id || '').toLowerCase().startsWith(_DRAIN_FOLLOW);
}

// Group escalations by action and origin, render each group as one item (N dupes = single Ack All)
function _groupEscs(escs) {
  const map = new Map();
  escs.forEach(e => {
    const key = e.action === 'improve_detection' ? e.id   // rules stay separate
      : `${_fromReassertion(e) ? 'reassertion' : 'other'}|${e.action}`;
    const origin = _fromDrain(e) ? `drain|${key}` : key;   // DRN1: the cut's cards, apart
    // JUG1: an action taken alone is never grouped with a card of another type on the same action
    // (a held isolation): the group's Ack would acknowledge it unread.
    const kind = _isExecuted(e) ? `executed|${origin}` : origin;
    if (!map.has(kind)) map.set(kind, []);
    map.get(kind).push(e);
  });
  return [...map.values()];
}

function _renderEscGroup(group) {
  const e     = group[0]; // most recent / representative
  const isSnapshotPending = _isSnapshotPending(e);
  const isModeHold        = _isHeld(e);
  const isWriteBlocked    = e.escalation_type === 'write_blocked';
  const isActionFailed    = e.escalation_type === 'action_failed';
  const pct    = e.confidence ? Math.round(e.confidence * 100) + '%' : '';
  const label  = isModeHold
    ? `${actionLabelVerb(e.action)}${pct ? ` (${pct})` : ''} — ${_heldWord(e)}`
    : _isExecuted(e)     ? `${actionLabel(e.action)} — done alone, to judge`
    : isSnapshotPending  ? 'Snapshot recommended'
    : isWriteBlocked     ? `${actionLabelVerb(e.action) || e.action || '?'} — write blocked`
    : isActionFailed     ? `${actionLabelVerb(e.action) || e.action || '?'} — failed`
    : _sharedTitle(group);
  const count = Number(group.length);
  const ids   = group.map(g => g.id).join(','); // CSV — one string argument of the button's action (_on)
  const isRule = e.action === 'improve_detection' && e.proposal_id;
  // proposed rule: Approve/Reject cover the decision — Ack is redundant
  const ruleButtons = isRule ? `
    <button class="action ok" ${_on('click', 'doApproveRule', e.proposal_id, e.id)} style="font-size:9px;padding:2px 7px">✓ Approve</button>
    <button class="action" ${_on('click', 'doRejectRule', e.proposal_id, e.id)} style="font-size:9px;padding:2px 7px;color:var(--red)">✗ Reject</button>` : '';
  // A card on a tile of its own opens that tile's cards (AL1c); a VM's, its VM's.
  const vmName = _ownTile(e) || e.resource_id.split('/').pop();
  const countBadge = count > 1
    ? `<span style="font-size:9px;font-weight:700;padding:1px 4px;border-radius:3px;
                    background:color-mix(in srgb,var(--purple) 15%,transparent);
                    color:var(--purple)">×${count}</span>` : '';
  // Recurrence (commit 87c066d): a persistent escalation stays ONE card but counts its
  // re-fires (occurrences) since first_seen → "this is lasting / repeating". Old
  // escalations without the field fall back to 1 (no badge).
  const occ = Number(e.occurrences) || 1;
  const recurBadge = occ > 1
    ? `<span title="${_attr(`Re-fired ${occ}× since ${e.first_seen || '?'}${e.last_seen ? ` (last ${e.last_seen})` : ''}`)}" style="font-size:9px;font-weight:700;padding:1px 4px;border-radius:3px;background:color-mix(in srgb,var(--orange) 15%,transparent);color:var(--orange);flex-shrink:0">↻ ${occ}×${e.first_seen ? ` · ${_relTime(e.first_seen)}` : ''}</span>`
    : '';
  // No Restore on an anchored card: it would restore a VM the detection does not name.
  const isRestore = e.action === 'restore_from_backup' && !_isAnchored(e);
  // ATT1 (#936): nor on a card that says it is unattributed, whatever its type.
  const restoreOffered = isRestore && !_unattributed(e);
  const isReadinessHold = e.escalation_type === 'readiness_hold';
  const actionBtns = isRule
    ? ruleButtons
    : isReadinessHold
    ? `<button class="action primary" ${_on('click', 'openActivation', vmName)} style="font-size:9px;padding:2px 7px">⚡ Review & turn on</button>
       <button class="action" ${_on('click', 'doAckAll', ids)} style="font-size:9px;padding:2px 7px">✓ Ack</button>
       <button class="action" ${_on('click', 'openCommandModal', e.id)} style="font-size:9px;padding:2px 7px">📋 Cmd</button>`
    : isModeHold
    ? `<button class="action primary" ${_on('click', 'doApproveAction', e.id, vmName)} style="font-size:9px;padding:2px 7px">▶ Approve & execute</button>
       <button class="action" ${_on('click', 'doAckAll', ids)} style="font-size:9px;padding:2px 7px">✓ Ack</button>
       <button class="action" ${_on('click', 'openCommandModal', e.id)} style="font-size:9px;padding:2px 7px">📋 Cmd</button>`
    : restoreOffered
    ? `<button class="action primary" ${_on('click', 'confirmRestore', vmName, e.id)} style="font-size:9px;padding:2px 7px">🔄 Restore</button>
       <button class="action" ${_on('click', 'doAckAll', ids)} style="font-size:9px;padding:2px 7px">✓ Ack</button>
       <button class="action" ${_on('click', 'openCommandModal', e.id)} style="font-size:9px;padding:2px 7px">📋 Cmd</button>`
    : isSnapshotPending
    ? `<button class="action" ${_on('click', 'doSnapshot', vmName)} style="font-size:9px;padding:2px 7px">📸 Snapshot</button>
       <button class="action" ${_on('click', 'doAckAll', ids)} style="font-size:9px;padding:2px 7px">✓ Ack</button>
       <button class="action" ${_on('click', 'openCommandModal', e.id)} style="font-size:9px;padding:2px 7px">📋 Cmd</button>`
    : `<button class="action" ${_on('click', 'doAckAll', ids)} style="font-size:9px;padding:2px 7px">✓ Ack</button>
       <button class="action" ${_on('click', 'openCommandModal', e.id)} style="font-size:9px;padding:2px 7px">📋 Cmd</button>`;
  // Observation (docs/observation.md): was this recommendation right? Decision cards only.
  const isDecision = !isRule && !_NOT_DECISIONS.has(e.escalation_type)
    && !String(e.signal_id || '').startsWith('reassert-');
  // The verdict is given in one place, TO JUDGE (decision of 26/10): the card leads there.
  // JUG3: a group of several cards to judge opens its window, where they are judged at once.
  const toJudgeHere = group.filter(x => !x.verdict && _toJudge.some(c => c.id === x.id));
  // Its window first: the card on top judged (not acknowledged), others of the group still to judge.
  const verdictBtns = isDecision
    ? (toJudgeHere.length > 1
      ? `<a class="judge-link" ${_on('click', 'openJudgeGroup', toJudgeHere.map(x => x.id).join(','))} title="Its cards to judge, several at once">to judge ×${Number(toJudgeHere.length)} ▸</a>`
      : e.verdict
      ? `<span style="font-size:9px;color:var(--dim);margin-left:auto">judged: ${_attr(e.verdict)}</span>`
      : `<a class="judge-link" ${_on('click', 'focusJudge', e.id)} title="Give it a verdict in TO JUDGE">to judge ▸</a>`)
    : '';
  // mode_hold/write_blocked/action_failed: type already encoded in title, keep ctx lean
  const ctxParts = _escCtx(e, pct, isModeHold || isWriteBlocked || isActionFailed, _sharedRuleTitle(group), _groupRules(group).size > 1);
  return `<div class="esc-item section-group s-escalation" style="margin-top:5px" ${_on('click', 'showEscModal', vmName)}>
    <div style="display:flex;align-items:flex-start;gap:5px;margin-bottom:3px">
      <span class="esc-action-label">${_attr(label)}</span>${e.source === 'exercise' ? `<span class="chip-exercise" title="An injector's exercise window covered this VM (run ${_attr(e.exercise_run || '?')}) — left out of the observation report">EXERCISE</span>` : ''}
      ${countBadge}
      ${recurBadge}
      <span style="color:var(--blue);font-size:10px;margin-left:auto;padding-top:1px;flex-shrink:0">▸ details</span>
    </div>
    ${ctxParts ? `<div class="esc-context">${ctxParts}</div>` : ''}
    ${_targetNote(e, vmName)}
    ${_restoreFailure(e)}
    <div style="display:flex;gap:5px;margin-top:6px;flex-wrap:wrap" ${_on('click', 'stop')}>${actionBtns}${verdictBtns}</div>
  </div>`;
}

async function doAckAll(ids) {
  if (typeof ids === 'string') ids = ids.split(',').filter(Boolean);
  try {
    await Promise.all(ids.map(id => _post(`/api/action/ack/${_seg(id)}`)));
    toast(`✓ Acknowledged (${ids.length})`);
    refreshState();
  } catch (e) {
    toast('✗ ' + e.message);
  }
}

// ── Topology rendering ─────────────────────────────────────────────────────────

let _expandedVms      = new Set();
let _collapsedVms     = new Set(); // user explicitly collapsed — immune to auto-expand
let _expandedBackends = new Set();
let _rulesCache       = [];   // flat array: a button's action takes the index, never the rule itself
let _coverageCache    = [];   // per-render {vmName, type, ip, placements} — index used by the N-NICs chip
let _nsgGlowCache     = [];   // per-render [vm_name,...] per NSG row — index used to glow governed VM cards on hover
let _pendingActions   = new Set(); // vm_names with in-flight release/unblock actions
let _cardOrder     = JSON.parse(localStorage.getItem('glorfindel_card_order') || '[]');
let _currentVmNames = [];
let _cardVmNames    = new Set(); // lowercased vm_names of the cards actually shown — the
                                 // honest denominator for "unprotected" (deduped like the cards)

// Build ordered slot array (vm_name | null) — always min 4 slots, always 1 extra empty
function _buildSlots(vmNames) {
  const minSize = Math.max(4, vmNames.length + 1);
  const slots = [..._cardOrder];
  while (slots.length < minSize) slots.push(null);
  // Remove stale VMs (no longer exist)
  const nameSet = new Set(vmNames);
  for (let i = 0; i < slots.length; i++) {
    if (slots[i] && !nameSet.has(slots[i])) slots[i] = null;
  }
  // Place new VMs into first available empty slot
  const inSlots = new Set(slots.filter(Boolean));
  for (const name of vmNames) {
    if (!inSlots.has(name)) {
      const ei = slots.findIndex(s => s === null);
      if (ei >= 0) slots[ei] = name; else slots.push(name);
    }
  }
  return slots;
}

function dropOnSlot(slotIdx, sourceName) {
  if (!sourceName) return;
  const slots = _buildSlots(_currentVmNames);
  const sourceIdx = slots.indexOf(sourceName);
  if (sourceIdx === slotIdx) return;
  const displaced = slots[slotIdx]; // null or another VM
  if (sourceIdx >= 0) slots[sourceIdx] = displaced;
  slots[slotIdx] = sourceName;
  _cardOrder = [...slots];
  localStorage.setItem('glorfindel_card_order', JSON.stringify(_cardOrder));
  renderInfra();
}

function toggleBackend(name) {
  if (_expandedBackends.has(name)) _expandedBackends.delete(name);
  else _expandedBackends.add(name);
  renderInfra();
}

function toggleAsset(vmName) {
  if (_expandedVms.has(vmName)) {
    _expandedVms.delete(vmName);
    _collapsedVms.add(vmName);
  } else {
    _expandedVms.add(vmName);
    _collapsedVms.delete(vmName);
  }
  renderInfra();
}

function _dot(color) {
  return `<span style="color:${color};font-size:10px">●</span>`;
}

// Cluster grouping key for an AKS node, from the explicit backend `parent` when present,
// else derived from the resource_id SHAPE (robust to a discovery that predates kind/parent).
// Two real-world shapes seen in the field:
//   - VMSS instance: .../virtualMachineScaleSets/<vmss>/virtualMachines/<n>  → parent VMSS id
//   - managed cluster: .../Microsoft.ContainerService/managedClusters/<name> → the cluster id
//     (AKS node heartbeats report the managedClusters id; all nodes share it = natural key)
// "" = not a cluster member. Single source of truth for folding nodes into one cluster card
// across discovered assets AND escalations (a posture_gap on a node must fold too).
// Glow the VM cards governed by a hovered NSG (PROTECT detail row → its `vms`).
function _glowNsgVms(idx, on) {
  (_nsgGlowCache[idx] || []).forEach(vm => {
    const el = document.getElementById(`asset-${vm}`);
    if (el) el.classList.toggle('nsg-glow', on);
  });
}

function _clusterKey(rid, parent) {
  if (parent) return parent;
  rid = rid || '';
  const vmss = rid.match(/^(.*\/virtualMachineScaleSets\/[^/]+)\/virtualMachines\//i);
  if (vmss) return vmss[1];
  if (/\/Microsoft\.ContainerService\/managedClusters\/[^/]+$/i.test(rid)) return rid;
  return '';
}



async function refreshActionsData() {
  const { resources = [] } = _state;
  const toFetch = resources
    .map(r => r.vm_name)
    .filter(vm => {
      const cached = _actionsCache[vm];
      return !cached || (Date.now() - cached.fetchedAt > 30000);
    });

  if (!toFetch.length) return;
  await Promise.all(toFetch.map(async vm => {
    try {
      const r = await fetch(`/api/actions/${_seg(vm)}?limit=15`);
      const d = await r.json();
      _actionsCache[vm] = { actions: d.actions || [], fetchedAt: Date.now() };
    } catch (e) {}
  }));
  renderInfra();
}

function renderInfra() {
  if (_configMode) return;
  const list           = document.getElementById('incidents-list');
  // The scroll container (#topo-graph), the edges' layer (#topo-svg) and #topo-body outlive a
  // refresh: only the content of #topo-body is replaced, never an element of the shell. Replaced
  // every 5 s with the rest, the container cut a scroll in progress (wheel, momentum, the scrollbar
  // held) and its position had to be put back by hand (TOPO1 #927). Built once, again only if one
  // of the three is missing — something else emptied the list (TOPO1b #949: #topo-body checked too).
  let graph = document.getElementById('topo-graph');
  let body  = graph && graph.querySelector('#topo-body');
  if (!graph || !list.contains(graph) || !body || !graph.querySelector('#topo-svg')) {
    list.innerHTML = `<div class="topo-graph" id="topo-graph"><svg class="topo-svg" id="topo-svg"></svg><div class="topo-body" id="topo-body"></div></div>`;
    graph = document.getElementById('topo-graph');
    body  = document.getElementById('topo-body');
  }
  // The PROTECT NSG list's own inner scroll is inside #topo-body: recreated, put back.
  const _prevNsg = document.getElementById('nsg-scroll');
  const _savedNsgScroll = _prevNsg ? _prevNsg.scrollTop : 0;
  const rules          = _cfgData?.detection?.rules     || [];
  const detectBackends  = _cfgData?.monitoring_backends  || [];
  const recoverBackends = (_cfgData?.assets || []).filter(a => a.type === 'azure_backup_vault');
  const discovered     = _state?.discovered_assets      || [];
  const knownResources = _cfgData?.known_resources      || [];
  const { resources = [], escalations = [], restores = [] } = _state;

  _escById = {};
  escalations.forEach(e => { _escById[e.id] = e; });
  _rulesCache = rules.slice(); // refresh index cache each render
  _coverageCache = [];         // rebuilt by _nicNote() during this render
  _nsgGlowCache  = [];         // rebuilt by the PROTECT NSG list during this render
  const restoreByVm = {};
  restores.forEach(r => { restoreByVm[r.vm_name] = r; });

  const detEscs = escalations.filter(e => e.action === 'improve_detection');
  const vmEscs  = escalations.filter(e => e.action !== 'improve_detection');

  const resourceMap = new Map();
  // Get-or-create the synthetic cluster card for a VMSS parent id. AKS nodes (VMSS
  // instances) fold into ONE cluster card per parent — see project_aks_display.
  const _getCluster = (parentId) => {
    let cl = resourceMap.get(parentId);
    if (!cl || !cl.is_cluster) {
      cl = { resource_id: parentId, vm_name: parentId.split('/').pop(),
             is_cluster: true, states: [], nodes: [], last_seen: null };
      resourceMap.set(parentId, cl);
    }
    return cl;
  };
  const _addClusterNode = (parentId, name, last_seen) => {
    const cl = _getCluster(parentId);
    // The managed-cluster resource itself is NOT one of its member nodes: an escalation
    // (e.g. a posture_gap) or a discovered entry keyed on the cluster id would otherwise
    // fold in as a phantom "<cluster> · no heartbeat" node (name === cluster short name).
    // Skip it as a node, but still let its last_seen refresh the cluster aggregate.
    if (name && name !== cl.vm_name && !cl.nodes.some(n => n.name === name))
      cl.nodes.push({ name, last_seen: last_seen || null });
    if (last_seen && (!cl.last_seen || last_seen > cl.last_seen)) cl.last_seen = last_seen;
  };
  knownResources.forEach(r => resourceMap.set(r.resource_id, { ...r, states: [] }));
  resources.forEach(r => {
    // A node with an ACTIVE state (isolated/blocked) keeps its own card — the incident +
    // its action buttons must stay visible, never hidden inside the cluster.
    if (resourceMap.has(r.resource_id)) resourceMap.get(r.resource_id).states = r.states;
    else resourceMap.set(r.resource_id, r);
  });
  // Discovered assets — 1:1 cards for standalone VMs; VMSS instances (AKS nodes) FOLD
  // into a cluster card. Membership is decided by _clusterKey (resource_id SHAPE: VMSS
  // with the explicit `parent`/`kind` as a hint — robust to a discovery cache that
  // predates those fields (that mismatch was making a cluster flip to a lone node card).
  // Carry last_seen so a powered-off VM (retained up to 8h) shows grayed, not vanishes.
  discovered.forEach(d => {
    const parentId = _clusterKey(d.resource_id, d.parent);
    if (parentId) { _addClusterNode(parentId, d.name, d.last_seen); return; }
    const existing = [...resourceMap.values()].find(r => r.vm_name === d.name);
    if (existing) {
      if (d.last_seen) existing.last_seen = d.last_seen;
      if (d.monitoring_backend) existing.monitoring_backend = d.monitoring_backend;
    } else {
      const key = d.resource_id || `discovered:${d.name}`;
      resourceMap.set(key, { resource_id: key, vm_name: d.name, states: [], last_seen: d.last_seen, monitoring_backend: d.monitoring_backend });
    }
  });
  vmEscs.forEach(e => {
    if (_isLocalState(e.resource_id)) return;
    if (_isWatchCard(e)) return;           // MBV1: on the GLORFINDEL node, never a tile without a name
    // AL1c: an identity card is on the identities' tile; a card about a group or the control
    // plane as a whole on a tile of its own — never a VM's, whatever its name.
    const own = _ownTile(e);
    if (own) {
      const t = _targetOf(e);
      if (!resourceMap.has(own))
        resourceMap.set(own, t.kind === 'identity'
          ? { resource_id: _IDENTITY_TILE, vm_name: own, label: 'Entra ID — identities', states: [], kind: 'identity' }
          : { resource_id: e.resource_id, vm_name: own, states: [], kind: t.kind,
              label: t.kind === 'control_plane' ? 'the control plane' : (t.name || e.resource_id.split('/').pop()) });
      return;
    }
    // An escalation on an AKS node (e.g. a stale posture_gap) folds into its cluster —
    // it must not spawn a bare node card. Actionable node states come via `resources`.
    const parentId = _clusterKey(e.resource_id, '');
    if (parentId) { _addClusterNode(parentId, e.resource_id.split('/').pop(), null); return; }
    const vmName = e.resource_id.split('/').pop();
    const exists = [...resourceMap.values()].some(r => r.vm_name === vmName);
    if (!exists)
      resourceMap.set(e.resource_id, {
        resource_id: e.resource_id,
        vm_name: vmName, states: [], is_nsg: _isNsgId(e.resource_id) });
  });
  // IDT1: Entra ID and the control plane always there while their rules run — not only with a card;
  // first in the row (the operator's order of the tiles, dragged, still wins).
  for (const kind of Object.keys(_WATCHED)) {
    const w = _WATCHED[kind];
    if (!resourceMap.has(w.tile) && _isWatched(kind))
      resourceMap.set(w.tile, { resource_id: w.resource_id, vm_name: w.tile, label: w.label, states: [], kind });
  }
  const _watchedFirst = [...resourceMap.entries()].sort(([, a], [, b]) => Number(Object.hasOwn(_WATCHED, b.kind || '')) - Number(Object.hasOwn(_WATCHED, a.kind || '')));
  resourceMap.clear(); _watchedFirst.forEach(([key, r]) => resourceMap.set(key, r));
  // What Glorfindel closed itself in the last day keeps its tile, VM or NSG.
  (_state.handled || []).forEach(h => {
    const name = (h.resource_id || '').split('/').pop();
    if (name && !_isLocalState(h.resource_id) && !_isIdentityId(h.resource_id) && !_clusterKey(h.resource_id, '') && ![...resourceMap.values()].some(r => r.vm_name === name))
      resourceMap.set(h.resource_id, { resource_id: h.resource_id, vm_name: name, states: [],
                                       is_nsg: _isNsgId(h.resource_id) });
  });
  _tiles = new Map([...resourceMap.values()].map(r => [r.vm_name, r]));

  // Card name set (deduped exactly like the rendered cards) — RECOVER uses this as the
  // "unprotected" denominator so the count always matches what the operator sees on
  // screen (e.g. an AKS cluster = one card, not its N node heartbeats).
  _cardVmNames = new Set(
    [...resourceMap.values()].filter(r => !r.is_nsg && !r.kind)   // an NSG, a group, an identity: no vault
      .map(r => (r.vm_name || '').toLowerCase()).filter(Boolean));

  // Auto-expand VMs with active incidents, unless user explicitly collapsed them
  // When incident clears, reset the collapsed preference so next incident re-expands
  [...resourceMap.values()].forEach(r => {
    const hasIncident = (r.states||[]).length > 0
      || vmEscs.some(e => _onTile(e, r));
    if (hasIncident && !_collapsedVms.has(r.vm_name)) _expandedVms.add(r.vm_name);
    if (!hasIncident) _collapsedVms.delete(r.vm_name); // allow re-expand on next incident; don't force-collapse user-expanded clean cards
  });

  body.innerHTML = `
      <!-- Layer 1 — Agent -->
      <div class="topo-layer">
        ${_renderAgentNode(rules, detectBackends, recoverBackends, discovered)}
      </div>

      <div class="topo-spacer"></div>

      <!-- Layer 2 — Modules -->
      <div class="topo-layer">
        ${_renderModules(rules, detectBackends, recoverBackends, resources)}
      </div>

      <div class="topo-spacer"></div>

      ${_exclusionsBand()}
      ${_auditBand()}

      <!-- Layer 3 — Assets -->
      <div class="topo-assets" id="topo-assets">
        ${(() => {
          _currentVmNames = [...resourceMap.values()].map(r => r.vm_name);
          const slots = _buildSlots(_currentVmNames);
          if (slots.every(s => !s)) {
            const msg = detectBackends.length
              ? 'No assets to show yet — powered-on VMs appear here once they emit a heartbeat'
              : 'No monitoring backends configured — add one in detection_rules.yaml';
            return `<div style="color:var(--dim);font-size:11px;padding:24px;text-align:center;width:100%">${msg}</div>`;
          }
          return slots.map((vmName, slotIdx) => {
            if (vmName) {
              const r = [...resourceMap.values()].find(r => r.vm_name === vmName);
              if (r) return r.is_cluster
                ? _renderClusterNode(r, slotIdx)
                : (r.is_nsg || r.kind)
                ? _renderNsgNode(r, vmEscs, slotIdx)
                : _renderAssetNode(r, vmEscs, detEscs, restoreByVm, slotIdx);
            }
            return `<div class="node-asset-empty"
              ${_on('dragover', 'dragOver')}
              ${_on('dragleave', 'dragLeave')}
              ${_on('drop', 'dropOn', slotIdx)}></div>`;
          }).join('');
        })()}
      </div>


      ${_legend()}`;

  if (_savedNsgScroll) {
    const _newNsg = document.getElementById('nsg-scroll');
    if (_newNsg) _newNsg.scrollTop = _savedNsgScroll;
  }
  _watchTopology(graph);
  _queueTopologyEdges();
  _applyReadOnlyGuards(list);
}

// The readiness audit not read, said once above the cards (TOPO1b #949, Jonathan 19/11 on a
// mockup; « ip ? » on every card set aside). Before, the cards lost their checks and their
// addresses in silence, and only the dot of the GLORFINDEL node went red. The last good audit
// kept: the band says when it was read. The reason comes from the browser or the server: escaped.
function _auditBand() {
  if (_auditStale) {
    const when = _auditLastRun ? `cards show the read of ${_attr(fmtTime(_auditLastRun))}` : 'cards show the last read';
    return `<div class="topo-band" role="status">⚠ Readiness audit not read: ${_attr(_auditStale)} <span class="topo-band-dim">· ${when}</span></div>`;
  }
  if (_auditData?.error)
    return `<div class="topo-band" role="status">⚠ Readiness audit not read: ${_attr(_auditData.error)} <span class="topo-band-dim">· checks and addresses unknown on every card · next try within 5 min</span></div>`;
  return '';
}

// The edges follow the map: drawn again, once per frame at most, when the map or its cards
// change size without a render — the window resized, the column beside it, a font loaded.
// Before, they stayed where the last render had put them (TOPO1 #927).
let _topoResize = null;
let _topoDrawQueued = false;
let _topoSeen = {};                     // the last size the observer saw, of the map and of its row
function _queueTopologyEdges() {
  if (_topoDrawQueued) return;
  _topoDrawQueued = true;
  requestAnimationFrame(() => { _topoDrawQueued = false; _drawTopologyEdges(); });
}
// Each render observes its new row of cards, and an observation starts with a notification: drawn
// on it, every refresh drew its edges twice (review of TOPO1). A size already seen draws nothing;
// a size that changed (a resize, a card grown without a render) draws again (TOPO1b #949).
function _onTopologyResize(entries) {
  let changed = false;
  for (const e of entries) {
    const role = e.target.id === 'topo-graph' ? 'graph' : 'assets';
    const size = `${Math.round(e.contentRect.width)}x${Math.round(e.contentRect.height)}`;
    if (_topoSeen[role] !== size) { _topoSeen[role] = size; changed = true; }
  }
  if (changed) _queueTopologyEdges();
}
// A browser without ResizeObserver: the edges are drawn at each render, not on a resize.
function _watchTopology(graph) {
  if (typeof ResizeObserver !== 'function') return;
  if (!_topoResize) _topoResize = new ResizeObserver(_onTopologyResize);
  _topoResize.disconnect();             // the cards' row of the last render is gone
  _topoResize.observe(graph);
  const assets = document.getElementById('topo-assets');
  if (assets) _topoResize.observe(assets);
}

function renderIncidents() { renderInfra(); }

// ── Agent node ─────────────────────────────────────────────────────────────────

function _renderAgentNode(rules, detectBackends, recoverBackends, discovered) {
  const moduleCount = Number(detectBackends.length) + Number(recoverBackends.length) + 1;
  // Parent node summarises its children: aggregate health of DETECT (rule polling)
  // and RECOVER (backup audit). Distinct from the header's `watch active` (engine
  // heartbeat) and `live` (UI freshness) — three different questions, no redundancy.
  const ruleErr      = rules.some(r => r.last_error);
  const rulesPolling = rules.length && rules.every(r => r.last_poll && !r.last_error);
  const restoreByVm  = (_auditData?.audits || []).map(a =>
    (a.checks || []).filter(c => c.action === 'restore_from_backup'));
  const auditChecks  = restoreByVm.flat();
  // The audit failing to run is a module error. A VM without a usable backup is the
  // fleet's posture, not a Glorfindel breakdown: orange, said as posture (seventh review, P3).
  const auditErr    = !!_auditData?.error;
  const postureGaps = restoreByVm.filter(cs => cs.some(c => c.status === 'fail')).length;
  const degraded    = auditChecks.some(c => c.status === 'warn') || (rules.length && !rulesPolling);
  const health = (ruleErr || auditErr)                    ? 'err'
               : (postureGaps || degraded)                ? 'warn'
               : (rules.length || auditChecks.length)     ? 'ok'
               :                                            'idle';
  const warnTitle = [
    postureGaps ? `Posture: ${postureGaps} VM${postureGaps > 1 ? 's' : ''} without a usable backup — the fleet, not Glorfindel` : '',
    degraded    ? 'A module is degraded' : '',
  ].filter(Boolean).join(' · ');
  const [dotColor, dotTitle] =
      health === 'err'  ? ['var(--red)',    'A module is in error']
    : health === 'warn' ? ['var(--orange)', warnTitle]
    : health === 'ok'   ? ['var(--green)',  'All modules healthy']
    :                     ['var(--dim)',    'Awaiting data'];
  const dot = `<span style="color:${dotColor}" title="${dotTitle}">●</span>`;

  return `<div class="node-agent" id="node-agent">
    <div class="node-agent-header">
      <span class="node-agent-title">GLORFINDEL</span>
      ${dot}
    </div>
    <div class="node-agent-stats">
      <span>${moduleCount} modules</span>
    </div>
    ${(_auditStale || _backupStale) ? `<div class="node-agent-stats" style="color:var(--orange);font-size:9px" title="A readiness fetch timed out — showing last known data">⚠ data stale</div>` : ''}
    ${_watchBand()}
  </div>`;
}

// ── The watch's own cards (MBV1, #1175; Jonathan 25/11, on a mockup) ─────────────────────────
// A card about no resource is the watch's: the model breaker's (`model_budget_tripped`, PRT2, written with
// `resource_id: ""`), or any other one to come. It was given a tile without a name, never drawn: nowhere
// on the page. Now on the GLORFINDEL node, a red band that opens them, each with its reason, its steps and
// its Ack; the header says the breaker's on every page (console.js). A card the page cannot place is
// never lost: whatever its type.
function _isWatchCard(e) { return !String((e && e.resource_id) || '').trim(); }
function _watchCards() { return (_state?.escalations || []).filter(_isWatchCard); }
function _watchBand() {
  const cards = _watchCards();
  if (!cards.length) return '';
  const breakers = cards.filter(e => e.escalation_type === 'model_budget_tripped').length;
  const others = cards.length - breakers;
  const last = cards.map(e => e.last_seen || e.first_seen || '').sort().pop();
  const what = [breakers ? `MODEL BREAKER ×${Number(breakers)}` : '',
                others ? `${Number(others)} card${others > 1 ? 's' : ''} of the watch` : ''].filter(Boolean).join(' · ');
  // A button: a key opens it too (the page's dispatch reads no key).
  return `<button type="button" class="node-watch" ${_on('click', 'openWatchCards')} title="Cards about the watch itself: open them">
      <span>${breakers ? '⚡' : '⚠'} <b>${_attr(what)}</b>${last ? ` · last ${_attr(Console.hms(last))} UTC` : ''}</span>
      <span class="node-watch-lnk">details ▸</span></button>`;
}
function openWatchCards() {
  const m = document.getElementById('modal');
  m.dataset.owner = 'watch-cards';
  document.getElementById('modal-cmd').style.display = 'none';
  document.getElementById('modal-cancel').style.display = 'none';
  const btn = document.getElementById('modal-confirm');
  btn.textContent = 'Close';
  btn.className = 'action';
  btn.onclick = () => { closeModal(); document.getElementById('modal-cancel').style.display = ''; };
  _renderWatchCards();
  document.querySelector('.modal').classList.add('wide');
  m.classList.add('open');
}
function _watchCardsOpen() {
  const m = document.getElementById('modal');
  return !!m && m.classList.contains('open') && m.dataset.owner === 'watch-cards';
}
// Each card whole: its reason is never cut (a breaker's says what stops and until when), its steps listed.
function _renderWatchCards() {
  const cards = _watchCards();
  document.getElementById('modal-title').textContent = `The watch — ${cards.length} card${cards.length === 1 ? '' : 's'}`;
  const body = document.getElementById('modal-body');
  body.innerHTML = !cards.length ? '<div class="watch-none">No card of the watch is open.</div>'
    : cards.map(e => {
      const steps = Array.isArray(e.suggested_steps) ? e.suggested_steps.filter(x => typeof x === 'string' && x.trim()) : [];
      return `<div class="watch-card">
        <div class="watch-card-t">${e.escalation_type === 'model_budget_tripped' ? '⚡' : '⚠'} ${_attr(escTitle(e))}
          <span class="judge-ts">${e.first_seen ? _relTime(e.first_seen) : ''}</span></div>
        <div class="watch-card-why">${_attr(e.reason || '')}</div>
        ${steps.length ? `<ol class="watch-card-steps">${steps.map(x => `<li>${_attr(x)}</li>`).join('')}</ol>` : ''}
        <div><button class="action" ${_on('click', 'ackWatchCards', e.id)}>✓ Ack</button></div>
      </div>`;
    }).join('') + (cards.length > 1
      ? `<div class="watch-all"><button class="action" ${_on('click', 'ackWatchCards', cards.map(e => e.id).join(','))}>✓ Ack all ${Number(cards.length)}</button></div>` : '')
    + (cards.some(e => e.escalation_type === 'model_budget_tripped') ? `<div class="watch-note">${_BREAKER_ACK}</div>` : '');
}
// The relecture of MBV1: an Ack closes the card, never the breaker — never told otherwise (a constant).
const _BREAKER_ACK = 'An Ack closes the card, not the breaker: the model comes back at 00:00 UTC (a provider\'s limit: once a call is served).';
// The Ack of the watch's cards: each answer read, a refusal said — never told done.
async function ackWatchCards(idsCsv) {
  const wanted = String(idsCsv || '').split(',').filter(id => _watchCards().some(e => e.id === id));
  if (!wanted.length) { toast('Already closed'); await refreshState(); return; }
  let ok = 0; const refused = [];
  for (const id of wanted) {
    try {
      const res = await _post(`/api/action/ack/${_seg(id)}`);
      const d = await res.json().catch(() => ({}));
      if (!res.ok || d.error) refused.push(String(d.error || d.detail || `HTTP ${res.status}`));
      else ok++;
    } catch (e) { refused.push(String(e.message || e)); }
  }
  toast(refused.length ? `⚠ ${ok} of ${wanted.length} acknowledged — ${refused[0]}` : `✓ Acknowledged (${ok})`);
  await refreshState();               // the node's band, and the window, read again
}

// ── Module nodes ───────────────────────────────────────────────────────────────

function _renderModules(rules, detectBackends, recoverBackends, resources) {
  // DETECT
  // A rule renders one of two ways: bound + polling (live coverage) or enabled===false
  // (couldn't resolve a backend, doesn't poll — 90a0b09). Disabled rules are grayed
  // with an "⚠ unbound" badge and excluded from the backend health dot, so they never
  // read as live coverage. Orphaned disabled rules (matching no backend) get their own
  // node below — invisible would be a false sense of coverage.
  const _ruleRow = (r) => {
    const idx = _rulesCache.indexOf(r);
    if (r.enabled === false) {
      return `<div class="row rule-item" ${_on('click', 'showRuleByIdx', idx)}
        style="padding:3px 4px;font-size:10px;opacity:.55">
        <span style="color:var(--dim);font-size:9px">●</span>
        <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${_attr(r.name)}">${_attr(r.name)}</span>
        ${r.ttp ? `<span style="color:var(--dim);font-size:9px">${_attr(r.ttp)}</span>` : ''}
        <span style="color:var(--orange);font-size:9px;margin-left:auto">⚠ unbound</span>
        <span style="color:var(--dim);font-size:9px">▸</span>
      </div>`;
    }
    const dc  = r.last_error ? 'var(--red)' : r.last_poll ? 'var(--green)' : 'var(--dim)';
    const mt  = r.last_match ? `<span style="color:${_matchColor(r.last_match)};font-size:9px;margin-left:auto;flex-shrink:0">${_relTime(r.last_match)}</span>` : '';
    // ADM1: the administrators' expected sudo set aside — counted here, never silent.
    // COR1: of them, the root shells whose every SSH session came from an expected origin.
    const exOrigin = r.origin_count > 0 ? `, ${r.origin_count} root shell(s) from an expected origin (COR1, ${_originProofTxt(r)})` : '';
    const ex  = r.expected_count > 0 ? `<span style="color:var(--dim);font-size:9px;flex-shrink:0" title="${_attr(`${r.expected_count} expected sudo set aside, no card (ADM1)${exOrigin} — glorfindel report`)}">${_attr(r.expected_count)} expected</span>` : '';
    // SLF1 (#929): the watch's own writes in its return channel, set aside — counted, never silent.
    const own = r.own_channel_count > 0 ? `<span style="color:var(--dim);font-size:9px;flex-shrink:0" title="${_attr(_ownChannelTxt(r))}">${_attr(r.own_channel_count)} own</span>` : '';
    // SLF2 (#1010): Orodruin's writes in its exercise channel, set aside — counted, never silent; its
    // identity unset or no object id, said on the line.
    const oro = Number(r.exercise_channel_count) > 0 || r.exercise_channel_config
      ? `<span style="color:${r.exercise_channel_config ? 'var(--orange)' : 'var(--dim)'};font-size:9px;flex-shrink:0" title="${_attr(_exerciseChannelTxt(r))}">${r.exercise_channel_config ? '⚠ Orodruin id' : `${_attr(Number(r.exercise_channel_count))} Orodruin`}</span>`
      : '';
    // MID1 (#981): the certificates Azure puts on the managed identities it creates, set aside —
    // counted, never silent; an id that is no object id, said on the line.
    const msi = Number(r.msi_certificate_count) > 0 || r.msi_certificate_config === 'malformed'
      ? `<span style="color:${r.msi_certificate_config === 'malformed' ? 'var(--orange)' : 'var(--dim)'};font-size:9px;flex-shrink:0" title="${_attr(_msiCertificateTxt(r))}">${r.msi_certificate_config === 'malformed' ? '⚠ MSI id' : `${_attr(Number(r.msi_certificate_count))} MSI`}</span>`
      : '';
    // SEC2d (#1147): the detections from an expected origin set aside (network_zones.expected_origins) —
    // counted, never silent.
    const eo = Number(r.expected_origin_count) > 0
      ? `<span style="color:var(--dim);font-size:9px;flex-shrink:0" title="${_attr(`${Number(r.expected_origin_count)} detection(s) from an expected origin set aside, no card (network_zones.expected_origins, SEC2d)`)}">${_attr(Number(r.expected_origin_count))} expected</span>`
      : '';
    return `<div class="row rule-item" ${_on('click', 'showRuleByIdx', idx)}
      style="padding:3px 4px;font-size:10px">
      <span style="color:${dc};font-size:9px">●</span>
      <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${_attr(r.name)}">${_attr(r.name)}</span>
      ${r.ttp ? `<span style="color:var(--dim);font-size:9px">${_attr(r.ttp)}</span>` : ''}
      ${ex}
      ${own}
      ${msi}
      ${eo}
      ${oro}
      ${mt}
      <span style="color:var(--dim);font-size:9px">▸</span>
    </div>`;
  };
  const detectNodes = detectBackends.map(b => {
    const bRules   = rules.filter(r => r.monitoring_backend_name === b.name);
    const liveRules = bRules.filter(r => r.enabled !== false);
    const unboundN  = bRules.length - liveRules.length;
    const hasErr   = liveRules.some(r => r.last_error);
    const allPoll  = liveRules.length && liveRules.every(r => r.last_poll && !r.last_error);
    const lastMatch = liveRules.reduce((m, r) => r.last_match && r.last_match > (m||'') ? r.last_match : m, null);
    // Backend-level reachability (commit 8b099de): reachable===false means the LAW is
    // gone/IAM-revoked/wrong-GUID → detection is BLIND. Authoritative over rule status;
    // null falls back to the rules. Kills the "green DETECT while the LAW is dead" lie.
    const unreachable = b.reachable === false;
    const backendErr  = b.last_error || '';
    const dot = unreachable          ? `<span style="color:var(--red)" title="${_attr(backendErr || 'backend unreachable')}">●</span>`
              : b.reachable === true ? `<span style="color:var(--green)">●</span>`
              : hasErr               ? `<span style="color:var(--red)">●</span>`
              : allPoll              ? `<span style="color:var(--green)">●</span>`
              : `<span style="color:var(--dim)">●</span>`;
    const expandId  = `rules-${b.name.replace(/[^a-z0-9]/gi,'-')}`;
    const isExpanded = _expandedBackends.has(b.name);
    const ruleRows  = bRules.map(_ruleRow).join('');
    return `<div class="node-backend detect ${unreachable ? 'state-error' : ''}" id="nb-${_attr(b.name)}" style="cursor:pointer;max-width:320px"
      ${_on('click', 'toggleBackend', b.name)}>
      <div class="node-backend-name">${dot} ${_attr(b.name)}</div>
      <div class="node-backend-type">${_attr(b.type)}</div>
      <div class="node-backend-row" style="justify-content:space-between">
        <span>${liveRules.length} rule${liveRules.length>1?'s':''}${unboundN ? ` <span style="color:var(--orange)">· ${unboundN} unbound</span>` : ''}</span>
        ${lastMatch ? `<span style="color:${_matchColor(lastMatch)};font-size:9px">match ${_relTime(lastMatch)}</span>` : ''}
        <span style="color:var(--blue);font-size:9px">${isExpanded ? '▾' : '▸'}</span>
      </div>
      ${unreachable ? `<div class="node-backend-row" style="color:var(--red);font-size:9px" title="${_attr(backendErr)}">⚠ unreachable — detection blind</div>`
        : hasErr ? `<div class="node-backend-row" style="color:var(--red);font-size:9px">⚠ error</div>` : ''}
      ${isExpanded ? `<div style="margin-top:6px;border-top:1px solid var(--border);padding-top:6px">${ruleRows}</div>` : ''}
    </div>`;
  }).join('') || `<div style="color:var(--dim);font-size:10px">No monitoring backends</div>`;

  // Disabled rules bound to no known backend would otherwise vanish — surface them
  // in a dim "unbound rules" node so the gap is visible (no false coverage).
  const _backendNames = new Set(detectBackends.map(b => b.name));
  const orphanRules = rules.filter(r => r.enabled === false && !_backendNames.has(r.monitoring_backend_name));
  const orphanExpanded = _expandedBackends.has('__unbound__');
  const orphanNode = orphanRules.length
    ? `<div class="node-backend detect state-warn" id="nb-__unbound__" style="cursor:pointer;max-width:320px;opacity:.85"
        ${_on('click', 'toggleBackend', '__unbound__')}>
        <div class="node-backend-name"><span style="color:var(--orange)">●</span> unbound rules</div>
        <div class="node-backend-type">no backend resolved</div>
        <div class="node-backend-row" style="justify-content:space-between">
          <span style="color:var(--orange)">${orphanRules.length} rule${orphanRules.length>1?'s':''} not polling</span>
          <span style="color:var(--blue);font-size:9px">${orphanExpanded ? '▾' : '▸'}</span>
        </div>
        ${orphanExpanded ? `<div style="margin-top:6px;border-top:1px solid var(--border);padding-top:6px">${orphanRules.map(_ruleRow).join('')}</div>` : ''}
      </div>`
    : '';

  // PROTECT — capacité de réaction du provider (pas un backend configuré)
  const isIsolated  = resources.some(r => r.states?.some(s => s.type === 'isolated'));
  const isBlocked   = resources.some(r => r.states?.some(s => s.type === 'blocked'));
  const isolCount   = resources.filter(r => r.states?.some(s => s.type === 'isolated')).length;
  const blockCount  = resources.reduce((n, r) =>
    n + (r.states||[]).filter(s => s.type === 'blocked').length, 0);
  const protectDot  = isIsolated ? `<span style="color:var(--red)">●</span>`
                    : isBlocked  ? `<span style="color:var(--orange)">●</span>`
                    :              `<span style="color:var(--green)">●</span>`;
  // PROTECT = the NSG layer. Subnet NSGs + their subnet-wide blocks live here;
  // VM-scoped blocks stay on the VM cards. Expandable: compact = NSG/action counts,
  // expanded = the subnet NSG(s) with their blocks.
  const subnetGroups = new Map();   // nsg → [{ip, since, vm_name}]
  const nsgKeys = new Set();
  resources.forEach(r => (r.states || []).forEach(s => {
    if ((s.type === 'blocked' || s.type === 'isolated') && s.nsg) nsgKeys.add(s.nsg);
    if (s.type === 'blocked' && s.scoped === false) {
      const key = s.nsg || 'subnet';
      if (!subnetGroups.has(key)) subnetGroups.set(key, []);
      subnetGroups.get(key).push({ ip: s.ip, since: s.since, vm_name: r.vm_name, nsg: s.nsg || '' });
    }
  }));
  // Full NSG landscape. Prefer the real NSG inventory (/api/nsgs, list_nsgs) — it counts
  // EVERY NSG as a resource (incl. subnet NSGs shared with a NIC's own, AKS subnet NSGs,
  // off-VM NSGs) which the per-VM audit under-counts. Fall back to the audit/state NSG
  // keys when the inventory hasn't loaded.
  const nsgInv = (_nsgItems && Array.isArray(_nsgItems.nsgs)) ? _nsgItems.nsgs : null;
  (_auditData?.audits || []).forEach(a => (a.checks || []).forEach(c => {
    if (c.status !== 'ok') return;             // a failed check names no NSG (IPS2)
    if (c.data && c.data.nsg) nsgKeys.add(c.data.nsg);
    (c.data?.nsgs || []).forEach(x => x.nsg && nsgKeys.add(x.nsg));
  }));
  const actionCount    = blockCount + isolCount;
  const protectExpanded = _expandedBackends.has('__protect__');
  const nsgN           = nsgInv ? Number(nsgInv.length) : (nsgKeys.size || subnetGroups.size);
  const restrictedN    = nsgInv ? nsgInv.filter(n => n.restricted).length : actionCount;
  // "Monitored" = an NSG governs ≥1 VM that LAW sees (discovered_assets). An NSG that
  // governs ONLY out-of-LAW VMs is a blind spot — Glorfindel can't detect/act there.
  const _discRids = new Set((_state?.discovered_assets || []).map(d => (d.resource_id || '').toLowerCase()).filter(Boolean));
  const _nsgMon   = n => (n.vms || []).some(v => _discRids.has((v || '').toLowerCase()));
  const blindN    = nsgInv ? nsgInv.filter(n => (n.vms || []).length && !_nsgMon(n)).length : 0;
  const blindSuffix = blindN ? ` · <span style="color:var(--red)" title="NSG(s) governing only VMs not in Log Analytics — Glorfindel is blind there">${blindN} blind-spot</span>` : '';
  const protectSummary = nsgInv
    ? `${nsgN} NSG${nsgN > 1 ? 's' : ''} · ${restrictedN ? `${restrictedN} carrying a Glorfindel action` : 'no Glorfindel action'}${blindSuffix}${_nsgStale ? ' · stale' : ''}`
    : (nsgN
        ? `${nsgN} NSG · ${actionCount ? actionCount + ' action' + (actionCount > 1 ? 's' : '') : 'no restrictions'}`
        : (actionCount ? `${actionCount} action${actionCount > 1 ? 's' : ''}` : 'no restrictions'));
  // Expanded: the full NSG list (associations + governed VMs + which carry a Glorfindel
  // rule). Hovering a row glows the VM card(s) it governs. Then the subnet-wide blocks.
  // Alphabetical order; the list is capped in height and scrolls (22 NSGs would make the
  // card endless otherwise). blind/restricted chips flag what needs attention in place.
  const nsgListDetail = nsgInv
    ? (nsgInv.length
        ? `<div id="nsg-scroll" style="max-height:240px;overflow-y:auto">${nsgInv.slice().sort((a, b) => (a.nsg || '').localeCompare(b.nsg || '')).map(n => {
            const sub = Number((n.subnets || []).length), nic = Number((n.nics || []).length);
            const govVms = n.vms || [];
            const assoc = [sub ? `${sub} subnet${sub > 1 ? 's' : ''}` : '', nic ? `${nic} NIC${nic > 1 ? 's' : ''}` : '', govVms.length ? `${Number(govVms.length)} VM${govVms.length > 1 ? 's' : ''}` : '']
              .filter(Boolean).join(' · ') || 'unassociated';
            const blind = govVms.length && !_nsgMon(n);
            const glowNames = [];
            govVms.forEach(v => {
              glowNames.push((v || '').split('/').pop());
              const ck = _clusterKey(v, ''); if (ck) glowNames.push(ck.split('/').pop());
            });
            const gi = _nsgGlowCache.push(glowNames) - 1;
            // Two lines so the NSG NAME gets the full width (it's what matters): name +
            // chips on top, the associations/rules metadata dimmed underneath.
            return `<div style="padding:4px;cursor:default"
              ${_on('mouseenter', '_glowNsgVms', gi, true)} ${_on('mouseleave', '_glowNsgVms', gi, false)}>
              <div style="display:flex;align-items:center;gap:6px;font-size:10px">
                <span style="color:${n.restricted ? 'var(--orange)' : 'var(--dim)'};font-size:9px">●</span>
                <span style="flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:600" title="${_attr(n.nsg)}">${_attr((n.nsg || '').split('/').pop())}</span>
                ${blind ? `<span style="color:var(--red);font-size:9px;flex-shrink:0" title="Governs only VMs not in Log Analytics — blind spot">⚠ blind</span>` : ''}
                ${n.quarantine
                  ? (n.restricted
                      ? `<span style="color:var(--orange);font-size:9px;flex-shrink:0" title="Glorfindel's quarantine NSG, attached: a VM is isolated">quarantine · active</span>`
                      : `<span style="color:var(--dim);font-size:9px;flex-shrink:0" title="Glorfindel's quarantine NSG, declared once and attached only to isolate a VM">quarantine · standby</span>`)
                  : n.restricted ? `<span style="color:var(--orange);font-size:9px;flex-shrink:0" title="Carries ${_attr(n.glorfindel_rules)} Glorfindel rule(s) — active isolation/block">restricted</span>` : ''}
              </div>
              <div style="color:var(--dim);font-size:9px;margin-left:15px">${assoc} · ${_attr(n.rules)} rule${n.rules > 1 ? 's' : ''}</div>
            </div>`;
          }).join('')}</div>`
        : `<div class="node-backend-row" style="color:var(--dim);font-size:9px">${_nsgItems.error ? 'NSG inventory error: ' + _attr(String(_nsgItems.error).slice(0, 80)) : 'No NSGs found'}</div>`)
    : '';
  const subnetDetail = [...subnetGroups.entries()].map(([nsg, ips]) => `
      <div style="margin-top:5px">
        <div style="font-size:9px;color:var(--orange);font-weight:600">🌐 ${_attr(nsg.split('/').pop())} · subnet-wide</div>
        ${ips.map(b => `
          <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-top:3px">
            <span class="badge blocked" style="font-size:9px;cursor:default">⚠ ${_attr(b.ip)} · ${age(b.since)}</span>
            <button class="action danger" ${_on('click', 'confirmUnblockIp', b.vm_name, b.ip, true, b.nsg)} style="font-size:9px;padding:1px 6px;margin-left:auto">↩️ Unblock</button>
          </div>`).join('')}
      </div>`).join('');
  const protectBody = protectExpanded
    ? `<div style="margin-top:6px;border-top:1px solid var(--border);padding-top:6px">
         ${nsgListDetail}
         ${subnetGroups.size ? `<div style="margin-top:6px;border-top:1px solid var(--border);padding-top:6px">${subnetDetail}</div>` : ''}
         ${!nsgInv && !subnetGroups.size ? '<div class="node-backend-row" style="color:var(--dim);font-size:9px">No subnet-wide blocks. VM-scoped blocks appear on each VM card.</div>' : ''}
       </div>`
    : '';
  const protectNode = `<div class="node-backend protect ${isIsolated ? 'state-error' : isBlocked ? 'state-warn' : ''}" id="module-protect"
      style="cursor:pointer" ${_on('click', 'toggleBackend', '__protect__')}>
    <div class="node-backend-name">${protectDot} network control</div>
    <div class="node-backend-type">cloud provider · NSG</div>
    <div class="node-backend-row" style="justify-content:space-between">
      <span style="color:${actionCount ? 'var(--orange)' : 'var(--green)'}">${protectSummary}</span>
      <span style="color:var(--blue);font-size:9px">${protectExpanded ? '▾' : '▸'}</span>
    </div>
    ${protectBody}
  </div>`;

  // RECOVER — sourced from the vault inventory (_backupItems), the RSV's protected
  // items, independent of VM discovery/power state. Expandable: compact = N protected
  // · oldest age; expanded = the list of items + last backup each.
  const recoverNodes = recoverBackends.map(b => {
    const inv   = _backupItems;                       // {vault, items, error} | null
    const invOk = inv && !inv.error && Array.isArray(inv.items);
    const items = invOk ? inv.items : [];
    const expanded = _expandedBackends.has(b.name);

    let pendingN = 0, oldest = 0, stoppedN = 0;
    items.forEach(it => {
      const st = (it.protection_state || '').toLowerCase();
      if (st.includes('stop') || st.includes('paus')) stoppedN++;
      if (it.latest_recovery_point == null) pendingN++;
      else if (typeof it.latest_age_h === 'number') oldest = Math.max(oldest, it.latest_age_h);
    });
    const worst = (inv && inv.error)        ? 'error'
                : (inv === null)            ? 'loading'
                : (items.length === 0)      ? 'empty'
                : (stoppedN || oldest > 48) ? 'warn'
                : (pendingN)                ? 'pending'
                :                             'ok';
    const [dotCol, sumCol] =
        worst === 'ok'                       ? ['var(--green)',  'var(--green)']
      : worst === 'warn' || worst === 'pending' ? ['var(--orange)', 'var(--orange)']
      : worst === 'error' || worst === 'empty' ? ['var(--red)',    'var(--red)']
      :                                        ['var(--dim)',    'var(--dim)'];
    // Cross-reference the VM cards on screen against the vault's protected items =
    // cards with NO backup. The count operators most want — "how many are NOT covered".
    // Denominator is _cardVmNames (deduped like the cards) so it matches the visible
    // card count, not the raw heartbeat count (AKS = 1 card, not N nodes).
    const _protectedNames = new Set(items.map(it => _backupVmName(it).toLowerCase()).filter(Boolean));
    let unprotectedN = 0;
    _cardVmNames.forEach(n => { if (!_protectedNames.has(n)) unprotectedN++; });
    const staleSfx = _backupStale ? ` · <span style="color:var(--orange)">stale</span>` : '';
    const summary = worst === 'error'   ? 'vault read error'
                  : worst === 'loading' ? 'loading…'
                  : worst === 'empty'   ? `no protected items${unprotectedN ? ` · <span style="color:var(--red)">${unprotectedN} unprotected</span>` : ''}`
                  : `${Number(items.length)} protected${unprotectedN ? ` · <span style="color:var(--red)">${unprotectedN} unprotected</span>` : ''}${oldest ? ` · oldest ${oldest}h` : ''}${pendingN ? ` · ${pendingN} pending` : ''}${stoppedN ? ` · ${stoppedN} stopped` : ''}${staleSfx}`;
    const itemRows = items.map(it => {
      const hasRP = it.latest_recovery_point != null;
      const age = hasRP ? _relTime(it.latest_recovery_point) : 'first backup pending';
      const col = !hasRP ? 'var(--orange)' : (it.latest_age_h > 48 ? 'var(--orange)' : 'var(--dim)');
      const st  = (it.protection_state || '').toLowerCase();
      const stopBadge = (st.includes('stop') || st.includes('paus'))
        ? ' <span style="color:var(--red);font-size:9px">⚠ stopped</span>' : '';
      return `<div class="row" style="padding:3px 4px;font-size:10px;display:flex;gap:6px;align-items:center">
        <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${_attr(it.name || '')}">${_attr(_backupVmName(it))}</span>${stopBadge}
        <span style="color:${col};font-size:9px;flex-shrink:0;white-space:nowrap">${age}</span>
      </div>`;
    }).join('');
    const body = expanded
      ? `<div style="margin-top:6px;border-top:1px solid var(--border);padding-top:6px">
           ${items.length ? itemRows
              : `<div class="node-backend-row" style="color:var(--dim);font-size:9px">${inv && inv.error ? 'Vault read error: ' + _attr(String(inv.error).slice(0, 80)) : 'No protected items in this vault — nothing is backed up'}</div>`}
           <div class="node-backend-row" style="margin-top:4px">
             <button class="action" style="font-size:9px;padding:1px 5px" ${_on('click', 'refreshBackups')}>↺ refresh</button>
           </div>
         </div>`
      : '';
    return `<div class="node-backend recover ${worst==='error'||worst==='empty'?'state-error':worst==='warn'||worst==='pending'?'state-warn':''}" id="nb-${_attr(b.name)}"
        style="cursor:pointer" ${_on('click', 'toggleBackend', b.name)}>
      <div class="node-backend-name"><span style="color:${dotCol}">●</span> ${_attr(b.name)}</div>
      <div class="node-backend-type">backup vault</div>
      <div class="node-backend-row" style="justify-content:space-between">
        <span style="color:${sumCol}">${summary}</span>
        <span style="color:var(--blue);font-size:9px">${expanded ? '▾' : '▸'}</span>
      </div>
      ${body}
    </div>`;
  }).join('') || `<div style="color:var(--dim);font-size:10px">No action backends</div>`;

  // Detection inert = no rule can poll a backend (no monitoring backend resolved, or
  // all rules disabled) → the system detects NOTHING. Honest signal > silence: shout it
  // above DETECT so an inert deployment never looks healthy. Pendant UI de la bannière CLI.
  const inertBanner = _cfgData?.detection?.inert
    ? `<div style="margin-bottom:6px;padding:5px 8px;border:1px solid var(--red);border-radius:5px;
         background:color-mix(in srgb, var(--red) 12%, transparent);color:var(--red);
         font-size:10px;font-weight:700;line-height:1.4">
         ⚠ DETECTION INERT — no monitoring backend resolved
         <div style="font-weight:400;color:var(--text);font-size:9px;margin-top:2px">
           No rule can poll — nothing is being detected. Configure a monitoring backend in glorfindel-config.yaml.
         </div>
       </div>`
    : '';
  return `<div class="topo-modules">
    <div class="topo-module">
      <div class="topo-module-label detect">DETECT</div>
      <div class="topo-module-nodes">${inertBanner}${detectNodes}${orphanNode}</div>
    </div>
    <div class="topo-module">
      <div class="topo-module-label protect">PROTECT</div>
      <div class="topo-module-nodes">${protectNode}</div>
    </div>
    <div class="topo-module">
      <div class="topo-module-label recover">RECOVER</div>
      <div class="topo-module-nodes">${recoverNodes}</div>
    </div>
  </div>`;
}

// ── Cluster node (AKS / VMSS — N nodes folded into one card) ────────────────────
// Glorfindel groups VMSS instances by `parent`; here we render one card per cluster
// with an aggregate (N nodes · X offline) and an expandable node list. Health is
// aggregated UI-side (a node is "offline" if its heartbeat is >15min stale, same
// threshold as VM cards). See project_aks_display.
function _renderClusterNode(cluster, slotIdx = 0) {
  const { vm_name, nodes = [] } = cluster;
  const isExpanded = _expandedVms.has(vm_name);
  const _nodeOffline = n =>
    !n.last_seen || (Date.now() - new Date(n.last_seen).getTime()) / 60000 > 15;
  const offlineN = nodes.filter(_nodeOffline).length;
  const dotCol = offlineN === nodes.length && nodes.length ? 'var(--dim)'
               : offlineN ? 'var(--orange)' : 'var(--cyan)';
  const summary = `${Number(nodes.length)} node${nodes.length > 1 ? 's' : ''}${offlineN ? ` · ${offlineN} offline` : ''}`;
  const nodeRows = nodes
    .slice()
    .sort((a, b) => (a.name || '').localeCompare(b.name || ''))
    .map(n => {
      const off = _nodeOffline(n);
      const short = (n.name || '').split('/').pop();
      return `<div style="display:flex;align-items:center;gap:6px;padding:3px 4px;font-size:10px">
        <span style="color:${off ? 'var(--dim)' : 'var(--green)'};font-size:9px">●</span>
        <span title="${_attr(n.name || short)}" style="flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${_attr(short)}</span>
        ${off
          ? `<span style="color:var(--dim);font-size:9px" title="${n.last_seen ? `last heartbeat ${_relTime(n.last_seen)}` : 'no recent heartbeat'}">${n.last_seen ? 'OFFLINE' : 'no heartbeat'}</span>`
          : `<span style="color:var(--green);font-size:9px">online</span>`}
      </div>`;
    }).join('');
  return `<div class="node-asset s-clean ${isExpanded ? 'expanded' : ''}"
    id="asset-${_attr(vm_name)}"
    draggable="true"
    ${_on('dragstart', 'dragVm', vm_name)}
    ${_on('dragend', 'dragEnd')}
    ${_on('dragover', 'dragOver')}
    ${_on('dragleave', 'dragLeave')}
    ${_on('drop', 'dropOn', slotIdx)}>
    <div class="node-asset-header" ${_on('click', 'toggleAsset', vm_name)}>
      <div style="display:flex;align-items:center;gap:6px">
        <span style="color:${dotCol};font-size:10px">●</span>
        <span class="node-asset-name" title="${_attr(vm_name)}">🎛 ${_attr(vm_name)}</span>
        <span style="font-size:8px;font-weight:700;padding:1px 5px;border-radius:3px;background:color-mix(in srgb,var(--cyan) 14%,transparent);color:var(--cyan);border:1px solid color-mix(in srgb,var(--cyan) 35%,var(--border));letter-spacing:.5px;flex-shrink:0">CLUSTER</span>
        <span style="color:var(--dim);font-size:9px;margin-left:auto;flex-shrink:0">${isExpanded ? '▾' : '▸'}</span>
      </div>
      <div style="display:flex;align-items:center;gap:6px;margin-top:5px">
        <span style="font-size:9px;color:${offlineN ? 'var(--orange)' : 'var(--dim)'}">${summary}</span>
      </div>
    </div>
    ${isExpanded ? `<div style="margin-top:6px;border-top:1px solid var(--border);padding-top:4px">${nodeRows}</div>` : ''}
  </div>`;
}

// What Glorfindel closed itself on this resource in the last day (/api/state `handled`).
function _handledLines(resource_id, name) {
  const mine = (_state.handled || []).filter(h =>
    h.resource_id === resource_id || (h.resource_id || '').split('/').pop() === name);
  return mine.map(h => `<div style="font-size:9px;color:var(--green);margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
      title="${_attr(h.resolution)}">✓ ${h.resolved_at ? `${_relTime(h.resolved_at)} · ` : ''}${_attr(h.resolution)}</div>`).join('');
}

// CFG2 (#1128): a VM exceptions[] takes never vanishes in silence. Its card stays, greyed, with a chip
// and a band: what is taken from it, why, by which pattern, and the rules written for it that still
// watch it — the sentence of glorfindel/exclusions.py (`said`), from the file the watch reads at its
// start. A reason is the operator's text: written through _attr, like everything from outside (#254).
const _EXCL_TIP = 'Read from exceptions[] in glorfindel-config.yaml. The watch applies it from its start: an exclusion written since waits for its restart.';
function _exclusionOf(name) {
  const vms = (_state?.exclusions || {}).vms || {};
  return Object.hasOwn(vms, name) ? vms[name] : null;
}
function _exclusionChip(name) {
  const x = _exclusionOf(name);
  if (!x) return '';
  return `<span class="excl-chip" title="${_attr(_EXCL_TIP)}">⊘ ${x.all ? 'EXCLUDED' : 'PARTLY EXCLUDED'}</span>`;
}
function _exclusionBand(name) {
  const x = _exclusionOf(name);
  if (!x) return '';
  return `<div class="excl-band" role="status" title="${_attr(_EXCL_TIP)}">${_attr(x.said)}</div>`;
}
// The exclusions not read (a config or rules the console can't read): said once above the cards —
// never a map that reads as « nothing excluded ».
function _exclusionsBand() {
  const err = (_state?.exclusions || {}).error;
  return err ? `<div class="topo-band" role="status">⚠ exceptions[] not read: ${_attr(err)} <span class="topo-band-dim">· a VM it takes can't be shown so on its card</span></div>` : '';
}

// A card on an NSG (I1F: a quarantine altered; A3: an orphan rule no VM holds): an NSG
// tile — its cards, nothing a VM has (mode, backup, snapshot, heartbeat). AL1c: the same tile
// for a card about a resource group, the control plane as a whole, or the identities.
const _TILE_BADGES = { nsg: ['🛡', 'NSG'], resource_group: ['▦', 'GROUP'],
  control_plane: ['☁', 'CONTROL PLANE'], identity: ['🪪', 'IDENTITIES'] };
function _renderNsgNode(resource, vmEscs, slotIdx = 0) {
  const { resource_id, vm_name } = resource;
  const badge = _TILE_BADGES[resource.kind] || _TILE_BADGES.nsg;
  const shown = resource.label || vm_name;
  const myEscs = vmEscs.filter(e => _onTile(e, resource));
  const isExpanded = _expandedVms.has(vm_name);
  const rg = (/\/resourcegroups\/([^/]+)/i.exec(resource_id || '') || [])[1] || '';
  // LEG1: only detections to judge on it (Entra ID, the control plane, a group): blue, as the line from
  // DETECT; any other card, purple.
  const judgeOnly = myEscs.length > 0 && myEscs.every(e => _DETECTION_ONLY.has(e.escalation_type));
  // IDT1: a watched tile says its health first on its dot — red a poll in error, grey its logs silent.
  const watched = Object.hasOwn(_WATCHED, resource.kind || '') && _isWatched(resource.kind);
  const health = watched ? _watchedHealth(resource.kind) : null;
  const dotColor = health && health.state === 'error' ? 'var(--red)' : health && health.state === 'silent' ? 'var(--dim)'
    : judgeOnly ? 'var(--blue)' : myEscs.length ? 'var(--purple)' : 'var(--green)';
  const dot = `<span style="color:${dotColor};font-size:10px"${health && health.said ? ` title="${_attr(health.said)}"` : ''}>●</span>`;
  const summary = myEscs.length
    ? `<span style="font-size:9px;color:${judgeOnly ? 'var(--blue)' : 'var(--purple)'}">${myEscs.length} card${myEscs.length > 1 ? 's' : ''}</span>`
    : `<span style="font-size:9px;color:var(--dim)">no open card</span>`;
  const cards = myEscs.length
    ? `<div class="vm-escalations" style="margin:8px 0 0;padding:8px 0 0;border-top:1px solid var(--border)">
        ${_groupEscs(myEscs).map(_renderEscGroup).join('')}</div>` : '';
  return `<div class="node-asset ${judgeOnly ? 's-judge' : myEscs.length ? 's-incident' : 's-clean'} ${isExpanded ? 'expanded' : ''}"
    id="asset-${_attr(vm_name)}" data-kind="${_attr(resource.kind || 'nsg')}"
    draggable="true"
    ${_on('dragstart', 'dragVm', vm_name)}
    ${_on('dragend', 'dragEnd')}
    ${_on('dragover', 'dragOver')}
    ${_on('dragleave', 'dragLeave')}
    ${_on('drop', 'dropOn', slotIdx)}>
    <div class="node-asset-header" ${_on('click', 'toggleAsset', vm_name)}>
      <div style="display:flex;align-items:center;gap:6px">
        ${dot}
        <span class="node-asset-name" title="${_attr(resource_id)}">${badge[0]} ${_attr(shown)}</span>
        <span style="font-size:8px;font-weight:700;padding:1px 5px;border-radius:3px;background:color-mix(in srgb,var(--orange) 14%,transparent);color:var(--orange);border:1px solid color-mix(in srgb,var(--orange) 35%,var(--border));letter-spacing:.5px;flex-shrink:0">${badge[1]}</span>
        <span style="color:var(--dim);font-size:9px;margin-left:auto;flex-shrink:0">${isExpanded ? '▾' : '▸'}</span>
      </div>
      <div style="display:flex;align-items:center;gap:6px;margin-top:5px">
        ${rg ? `<span style="font-size:9px;color:var(--dim)">${_attr(rg)}</span>` : ''}
        ${summary}
      </div>
      ${watched ? `<div style="margin-top:4px">${_watchedLine(resource.kind, health)}</div>` : ''}
      ${_handledLines(resource_id, vm_name)}
    </div>
    ${isExpanded && watched ? _watchedBlock(resource.kind, health) : ''}
    ${isExpanded ? cards : ''}
  </div>`;
}

// ── Asset nodes ────────────────────────────────────────────────────────────────

// ── A VM's own addresses (IPS1, #931) ──────────────────────────────────────────
// Read by the NSG audit, NIC by NIC: `ips` (its private addresses) and `public_ips` (IPS1a: each
// `{address}`, or `{address: null, error}` when its read failed). On the card folded and unfolded
// (Jonathan, 19/11, option A): Ctrl+F finds the VM of an address without opening a card, and a
// public address shows a VM the Internet can reach. Never an attacker's address: those are the
// BLOCKED badges, below. Everything here comes from Azure: escaped, never written raw (#254).
const _ADDR_FOLDED = 4;   // private addresses on the folded line, then « +N »
// IPS2 (#950, Jonathan 19/11 on a mockup): a VM without an NSG on its NIC nor on its subnet shows its
// addresses all the same — IPS2a: its « NSG access » check stays `fail` but carries `data.nsgs`, a NIC
// without NSG at `nsg_scope: "none"`. A failed check is never read as a good one: its addresses are
// shown, its checks and buttons stay those of a failure (`failed`, the ✗ of the readiness).
function _vmNet(auditEntry) {
  if (!auditEntry) return null;                       // not audited (yet): nothing said
  const check = (auditEntry.checks || []).find(c => c.name === 'NSG access');
  const nsgs = Array.isArray(check?.data?.nsgs) ? check.data.nsgs : [];
  const failed = !check || check.status !== 'ok';
  if (failed && !nsgs.length) return { unread: (check && check.message) || 'no NSG audit for this VM' };
  return {
    at: auditEntry.timestamp,
    failed: failed ? String(check.message || 'NSG audit failed') : '',
    nics: nsgs.map(x => ({
      nic: String(x?.nic_id || '').split('/').pop(),
      bare: x?.nsg_scope === 'none',                  // nothing filters this NIC (IPS2)
      ips: (Array.isArray(x?.ips) ? x.ips : []).filter(Boolean).map(String),
      pubs: (Array.isArray(x?.public_ips) ? x.public_ips : []).filter(p => p && typeof p === 'object'),
    })),
  };
}
// A NIC without NSG, nor on its subnet: said once on the card, in the row of its mode (IPS2).
function _bareChip(net) {
  const bare = (net && net.nics || []).filter(n => n.bare);
  if (!bare.length) return '';
  return `<span class="vm-bare" title="${_attr('No NSG on ' + bare.map(n => n.nic || 'a NIC').join(', ') + ' nor on its subnet: nothing filters its traffic')}">NO NSG</span>`;
}
function _addrBtn(a, pub) {
  return `<button type="button" class="vm-ip${pub ? ' pub' : ''}" ${_on('click', 'copyAddr', String(a))} title="${_attr('Copy ' + a)}">${_attr(a)}</button>`;
}
// Why a public IP did not read, in the page's language: IPS2a gives a code beside its own words
// (French, free text, never matched). A code the page does not know: the words as they are.
const _PUB_REASONS = {
  forbidden: 'access denied (Reader missing on its resource group?)',
  not_found: 'not found (deleted?)',
  not_allocated: 'no address allocated (a dynamic IP on a stopped VM?)',
  unreadable: 'unreadable',
};
function _pubReason(p) {
  const words = String(p.error || 'unknown');
  const said = Object.prototype.hasOwnProperty.call(_PUB_REASONS, p.code) ? _PUB_REASONS[p.code] : '';
  return { said: said || words, words: said ? words : '' };
}
// A public IP whose address did not read is said, never left out: the VM is still exposed. On a NIC
// without NSG (`bare`), the address in red: nothing filters it (IPS2).
function _pubAddr(p, unfolded, bare) {
  if (p.address) {
    const a = String(p.address);
    if (bare) return `<span class="vm-pub bare" title="${_attr('No NSG on the NIC nor on its subnet: nothing filters ' + a)}">🌐 ${_addrBtn(a, true)}${unfolded ? ' <span class="vm-pubtag">PUBLIC</span>' : ''}</span>`;
    return `<span class="vm-pub">🌐 ${_addrBtn(a, true)}${unfolded ? ' <span class="vm-pubtag">PUBLIC</span>' : ''}</span>`;
  }
  const why = _pubReason(p);
  return unfolded
    ? `<span class="vm-pub unread"${why.words ? ` title="${_attr(why.words)}"` : ''}>🌐 public IP not read: ${_attr(why.said)}</span>`
    : `<span class="vm-pub unread" title="${_attr('Public IP not read: ' + why.said)}">🌐 ?</span>`;
}
function _addrLine(net) {
  if (!net) return '';
  if (net.unread) return `<div class="vm-addr" title="${_attr('Addresses not read: ' + net.unread)}">ip —</div>`;
  const priv = [...new Set(net.nics.flatMap(n => n.ips))];
  const pubs = net.nics.flatMap(n => n.pubs.map(p => [p, n.bare]));
  if (!priv.length && !pubs.length) return `<div class="vm-addr" title="No address on the VM's NICs">ip —</div>`;
  const more = priv.length > _ADDR_FOLDED ? `<span title="Unfold the card for every address">+${Number(priv.length - _ADDR_FOLDED)}</span>` : '';
  return `<div class="vm-addr">${priv.slice(0, _ADDR_FOLDED).map(a => _addrBtn(a, false)).join('')}${more}${pubs.map(([p, bare]) => _pubAddr(p, false, bare)).join('')}</div>`;
}
function _netBlock(net) {
  if (!net) return '';
  if (net.unread) return `<div class="vm-net"><span class="vm-netfoot">addresses not read — ${_attr(net.unread)}</span></div>`;
  const nics = net.nics.map(n => `<div class="vm-nic"><span class="vm-nicname">⇄ ${_attr(n.nic || 'NIC')}${n.bare ? ' · <span class="vm-bare-txt">no NSG</span>' : ''}</span>${n.ips.map(a => _addrBtn(a, false)).join('')}${n.pubs.map(p => _pubAddr(p, true, n.bare)).join('')}</div>`).join('');
  const failed = net.failed ? `<div class="vm-netfoot">NSG audit failed: ${_attr(net.failed)}</div>` : '';
  return `<div class="vm-net">${nics}${failed}<div class="vm-netfoot">read by the NSG audit ${_attr(_relTime(net.at))}</div></div>`;
}
// ── A VM's identity (VMI1, #971, Jonathan 20/11 on a mockup, option A) ─────────────
// What the page knows of the VM already — its id, where its subscription and its group are read,
// the backend that discovered it, its last heartbeat — said on hover of its name, and on the
// unfolded card in a block where each field is copied in one click. The name still unfolds the
// card. A phone has no hover: there, the block. Everything comes from Azure or the discovery: escaped.
function _vmIdentity(resource) {
  const id = String(resource.resource_id || '');
  const m = /\/subscriptions\/([^/]+)\/resourceGroups\/([^/]+)\//i.exec(id);
  return {
    name: String(resource.vm_name || id.split('/').pop() || ''),
    rg: m ? m[2] : '', sub: m ? m[1] : '',
    id: id.startsWith('/subscriptions/') ? id : '',   // a discovered name without its id: no id said
    ws: String(resource.monitoring_backend || ''),
    seen: resource.last_seen ? _relTime(resource.last_seen) : '',
  };
}
// The name's tooltip, one field a line (the browser's own: no copy from it; the block copies).
function _identityTip(v) {
  const detected = v.ws ? `${v.ws}${v.seen ? ' · heartbeat ' + v.seen : ''}` : (v.seen ? 'heartbeat ' + v.seen : '');
  return [v.name, v.rg && `resource group  ${v.rg}`, v.sub && `subscription    ${v.sub}`,
          detected && `detected by     ${detected}`, v.id].filter(Boolean).join('\n');
}
// The value is the button: a copy outside a secure context selects the button's own text (copyAddr).
function _idBlock(v) {
  const row = (k, val, long) => val
    ? `<span class="vm-id-k">${k}</span><button type="button" class="vm-ip${long ? ' long' : ''}" ${_on('click', 'copyAddr', val)} title="${_attr('Copy the ' + k + (long ? ': ' + val : ''))}">${_attr(val)}</button>`
    : '';
  const detected = v.ws ? `${v.ws}${v.seen ? ' · ' + v.seen : ''}` : '';
  const rows = [row('name', v.name), row('group', v.rg), row('subscription', v.sub), row('resource id', v.id, true),
                detected ? `<span class="vm-id-k">detected by</span><span>${_attr(detected)}</span>` : ''].join('');
  return rows ? `<div class="vm-id">${rows}</div>` : '';
}

// A copy by the clipboard where the page may write it (a secure context: the loopback, the SSH
// tunnel). Elsewhere (a plain http address of the tailnet), the address selected and copied by the
// browser at once, during the click: a selection left for Ctrl+C would go with the next refresh,
// 5 s at most. The address is selectable (`.vm-ip`: user-select, the card being draggable sets
// none). The toast says what happened, never a copy that did not (review of IPS1b, measured).
function copyAddr(a) {
  const el = _target;
  const text = String(a);
  // A long value (a resource id, VMI1) shortened in the toast only: its start and its end. The copy is whole.
  const shown = text.length > 48 ? `${text.slice(0, 18)}…${text.slice(-26)}` : text;
  const byBrowser = () => {
    const r = document.createRange(); r.selectNodeContents(el);
    const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    let copied = false;
    try { copied = String(s) === text && document.execCommand('copy'); } catch (e) { copied = false; }
    s.removeAllRanges();
    toast(copied ? `✓ ${shown} copied` : `✗ ${shown} not copied — select it and copy it by hand`);
  };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(() => toast(`✓ ${shown} copied`), byBrowser);
  else byBrowser();
}

function _renderAssetNode(resource, vmEscs, detEscs, restoreByVm, slotIdx = 0) {
  const { resource_id, vm_name, states: _rawStates = [], last_seen, monitoring_backend } = resource;
  // Subnet-wide blocks live on the shared subnet NSG, not on this VM — they're shown
  // on a dedicated subnet NSG card, so exclude them from every VM-card view here.
  const states = _rawStates.filter(s => !(s.type === 'blocked' && s.scoped === false));
  const isIsolated  = states.some(s => s.type === 'isolated');
  const isBlocked   = states.some(s => s.type === 'blocked');
  const restoreInfo = restoreByVm[vm_name];
  const myEscs      = vmEscs.filter(e => _onTile(e, resource));
  const myDetEscs   = (detEscs||[]).filter(e =>
    e.resource_id === resource_id || e.resource_id.split('/').pop() === vm_name);
  const totalEscs   = myEscs.length + myDetEscs.length;
  const isExpanded  = _expandedVms.has(vm_name);

  // "Possibly offline": no heartbeat. Backend retains a VM in discovery up to 8h, then
  // evicts it (last_seen gone). Two offline signals, both excluding states that
  // legitimately stop the heartbeat without the VM being down — isolation (NSG deny-all
  // cuts AMA) and an in-flight restore (VM deallocated):
  //   (a) still in discovery but heartbeat stale (>15 min), OR
  //   (b) evicted from discovery (no last_seen) yet still rendered because it has an
  //       active state — a block (incl. a subnet-wide one filtered off the VM view)
  //       doesn't cut AMA, so absence from discovery means it stopped reporting >8h ago.
  // Three mutually-exclusive "monitoring blindness" states, in precedence order (most
  // blind first) so a card shows exactly ONE — no OFFLINE+STALE doublon:
  //   UNMONITORED — never in discovery, card exists only from an escalation → not monitored
  //   STALE       — monitoring backend (LAW) unreachable → last_seen frozen, unverifiable
  //   OFFLINE     — in discovery but heartbeat stale (>15m) / evicted (>8h) → silent (off?)
  const _gapMin   = last_seen ? (Date.now() - new Date(last_seen).getTime()) / 60000 : null;
  const _evicted  = _gapMin === null && _rawStates.length > 0;
  // (a) UNMONITORED — no discovery, no active state, only an escalation references it.
  const isUnmonitored = _gapMin === null && _rawStates.length === 0
                        && myEscs.length > 0 && !isIsolated && !restoreInfo;
  // (b) STALE — the backend that would heartbeat this VM is down; discovery keeps the
  // cache on a backend failure (by contract), so a "fresh" last_seen is a lie here.
  const _vmBackend = monitoring_backend
    ? (_cfgData?.monitoring_backends || []).find(b => b.name === monitoring_backend) : null;
  // !isUnmonitored makes the precedence explicit: UNMONITORED always wins over STALE
  // (guaranteed exclusive, not just relying on the discovery data invariant).
  const isStale = _vmBackend && _vmBackend.reachable === false
                  && !isUnmonitored && !isIsolated && !restoreInfo;
  // (c) OFFLINE — only when neither more-blind state holds (a dead backend can't tell us
  // the VM is silent; an escalation-only card was never heartbeating).
  const isOffline = !isIsolated && !restoreInfo && !isStale && !isUnmonitored
                    && ((_gapMin !== null && _gapMin > 15) || _evicted);

  // LEG1: a VM's cards all detections to judge (the control plane's, filed on it: a disk's access, a role
  // on it — card_target.py): blue, as their line from DETECT.
  const judgeOnly = myEscs.length > 0 && myEscs.every(e => _DETECTION_ONLY.has(e.escalation_type));
  const stateClass = _pendingActions.has(vm_name) ? 's-releasing'
                   : restoreInfo    ? 's-restoring'
                   : (isIsolated && isBlocked) ? 's-both'
                   : isIsolated     ? 's-isolated'
                   : isBlocked      ? 's-blocked'
                   : myEscs.length  ? (judgeOnly ? 's-judge' : 's-incident')   // LEG1: detections to judge, blue
                   : 's-clean';

  const dot = restoreInfo   ? `<span class="dot-pulse" style="color:var(--green)">●</span>`
            : isIsolated    ? `<span style="color:var(--red)">●</span>`
            : isBlocked     ? `<span style="color:var(--orange)">●</span>`
            : myEscs.length ? `<span style="color:${judgeOnly ? 'var(--blue)' : 'var(--purple)'}">●</span>`
            : isStale       ? `<span style="color:var(--dim)" title="monitoring backend unreachable — state unverifiable">●</span>`
            : isOffline     ? `<span style="color:var(--dim)" title="possibly offline">●</span>`
            :                 `<span style="color:var(--green)">●</span>`;

  const _offlineTitle = last_seen
    ? `No heartbeat for ${_relTime(last_seen)} — possibly powered off`
    : `No recent heartbeat — dropped from discovery (off > retention window), kept visible by an active block`;
  const offlineBadge = isOffline
    ? `<span title="${_offlineTitle}" style="font-size:8px;font-weight:700;padding:1px 5px;border-radius:3px;background:color-mix(in srgb,var(--dim) 14%,transparent);color:var(--dim);border:1px solid var(--border);letter-spacing:.5px;flex-shrink:0">OFFLINE</span>`
    : '';
  const unmonitoredBadge = isUnmonitored
    ? `<span title="No Log Analytics heartbeat and not in discovery — this card exists only from an escalation. Glorfindel isn't monitoring this resource." style="font-size:8px;font-weight:700;padding:1px 5px;border-radius:3px;background:color-mix(in srgb,var(--dim) 14%,transparent);color:var(--dim);border:1px solid var(--border);letter-spacing:.5px;flex-shrink:0">UNMONITORED</span>`
    : '';
  const staleBadge = isStale
    ? `<span title="${_attr(`Monitoring backend '${monitoring_backend}' unreachable${_vmBackend.last_error ? ' — ' + _vmBackend.last_error : ''}. last_seen is frozen — VM state cannot be verified.`)}" style="font-size:8px;font-weight:700;padding:1px 5px;border-radius:3px;background:color-mix(in srgb,var(--orange) 14%,transparent);color:var(--orange);border:1px solid color-mix(in srgb,var(--orange) 35%,var(--border));letter-spacing:.5px;flex-shrink:0">STALE</span>`
    : '';

  // Badges are clickable in compact mode only — expanded mode uses dec-row / esc-items
  const escBadge = totalEscs
    ? `<span ${!isExpanded ? `${_on('click', 'showEscModal', vm_name)}` : ''}
        style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:4px;
               ${!isExpanded ? 'cursor:pointer;' : ''}
               background:color-mix(in srgb,var(--purple) 18%,transparent);
               color:var(--purple);border:1px solid color-mix(in srgb,var(--purple) 45%,transparent)">
        ${totalEscs} escalation${totalEscs > 1 ? 's' : ''}${!isExpanded ? ' ▸' : ''}</span>`
    : '';

  // Several blocks: one summary line, the list in its window (CON-K) — one badge per IP made the
  // card as long as the list.
  const blocks = _blocksOf(states);
  const stateBadges = [
    restoreInfo ? `<span class="badge restoring" style="font-size:9px">🔄 RESTORING · ${_attr(restoreInfo.elapsed_label)}</span>` : '',
    ...states.filter(s => s.type === 'isolated').map(s =>
      `<span class="badge isolated" style="font-size:9px${!isExpanded ? ';cursor:pointer' : ''}"
           ${!isExpanded ? `${_on('click', 'showIsolationModal', vm_name)}` : ''}>ISOLATED · ${age(s.since)}</span>${_scopeNote(s)}${_nicNote(s, vm_name)}${_doorNote(s)}`),
    ...(blocks.length > 1 ? [_blocksSummary(blocks, resource_id)] : blocks.map(s =>
      `<span class="badge blocked" style="font-size:9px${!isExpanded ? ';cursor:pointer' : ''}"
           ${!isExpanded ? `${_on('click', 'showIsolationModal', vm_name)}` : ''}>BLOCKED ${_attr(s.ip)} · ${age(s.since)}</span>${_scopeNote(s)}${_nicNote(s, vm_name)}`)),
    escBadge,
  ].filter(Boolean).join('');

  const auditEntry = (_auditData?.audits || []).find(a => a.resource_id === resource_id);
  const net        = _vmNet(auditEntry);              // its addresses (IPS1)
  const ident      = _vmIdentity(resource);           // its id, group, subscription (VMI1)
  const readiness  = auditEntry
    ? ACTION_GROUPS.map(g => {
        const st = _worstStatus(auditEntry.checks, g.actions);
        const [ic, col] = st==='ok' ? ['✓','var(--green)'] : st==='warn' ? ['⚠','var(--orange)']
                        : st==='fail' ? ['✗','var(--red)'] : ['—','var(--dim)'];
        const detail = _groupDetail(auditEntry.checks, g.actions);
        return `<span style="font-size:11px;color:${col}" title="${_attr(`${g.label}: ${st}${detail ? '\n' + detail : ''}`)}">${ic}</span>`;
      }).join(' ')
    : '';

  const cached = _actionsCache[vm_name];
  const escalatedActions = new Set(myEscs.map(e => e.action));
  const seenDecActions   = new Set();

  // Build dec-rows: autonomous actions only, deduplicated, state badge + correction button merged in
  const filteredDecs = (cached?.actions || [])
    .map((a, realIdx) => ({ a, realIdx }))
    .filter(({ a }) => {
      if (a.action === 'improve_detection')                return false;
      if (escalatedActions.has(a.action))                  return false;
      if (seenDecActions.has(a.action))                    return false;
      // Hide state-coupled actions when state is no longer active
      if (a.action === 'isolate_vm'          && !isIsolated) return false;
      if (a.action === 'block_suspicious_ip' && !isBlocked)  return false;
      // Admin/recovery/destructive actions — noise once resolved, handled via esc-item when pending
      if (['release_isolation', 'revoke_temp_access',
           'restore_from_backup', 'delete_resource',
           'wipe_storage', 'modify_network_rule', 'escalate_permissions'].includes(a.action)) return false;
      seenDecActions.add(a.action);
      return true;
    })
    .slice(0, 2);

  const coveredByDec = new Set(filteredDecs.map(({ a }) => a.action));

  const decisionHtml = filteredDecs.map(({ a, realIdx }) => {
    const pct = a.confidence ? Math.round(a.confidence * 100) + '%' : '';
    const hasDetail = !!a.full_reasoning;

    // State badge + correction button for matching autonomous actions
    let badge = '';
    let corrBtn = '';
    if (a.action === 'isolate_vm' && isIsolated) {
      const s = states.find(s => s.type === 'isolated');
      badge   = s ? `<span class="badge isolated" style="font-size:9px;cursor:default">ISOLATED · ${age(s.since)}</span>${_scopeNote(s)}${_nicNote(s, vm_name)}${_doorNote(s)}` : '';
      corrBtn = `<button class="action danger" ${_on('click', 'confirmRelease', vm_name)} style="font-size:9px;padding:2px 7px;margin-left:auto">↩️ Release</button>`;
    } else if (a.action === 'block_suspicious_ip' && isBlocked) {
      // The latest decision keeps its row; the blocks are all said, never the first one alone
      // (CON-K: it hid the others) — one shown with its buttons, several in their window.
      badge   = blocks.length > 1 ? _blocksSummary(blocks, resource_id) : _blockBadge(blocks[0], vm_name);
      corrBtn = blocks.length > 1 ? _manageBtn(blocks, resource_id) : _blockBtns(blocks[0], vm_name);
    }

    const meta = [
      pct   ? `<span class="dec-conf">${pct}</span>` : '',
      a.ttp ? `<span class="dec-ttp">${_attr(a.ttp)}</span>` : '',
    ].filter(Boolean).join('');

    const sectionClass = corrBtn ? 's-protect' : '';
    return `<div class="section-group ${sectionClass}" style="margin-top:5px">
      ${badge ? `<div style="margin-bottom:3px">${badge}</div>` : ''}
      <div class="dec-row ${hasDetail ? 'dec-clickable' : ''}"
        ${hasDetail ? `${_on('click', 'showReasoning', vm_name, Number(realIdx))}` : ''}>
        <div class="dec-header">
          <span class="dec-action">${_attr(actionLabel(a.action))}</span>
          ${hasDetail ? `<span style="color:var(--blue);font-size:10px;margin-left:6px">▸ reasoning</span>` : ''}
        </div>
        ${meta ? `<div class="dec-meta">${meta}</div>` : ''}
      </div>
      ${corrBtn ? `<div style="margin-top:5px;display:flex;gap:6px;flex-wrap:wrap;align-items:center">${corrBtn}</div>` : ''}
    </div>`;
  }).join('');

  // Fallback: states with no matching dec-row (cache miss) — show badge + button standalone
  const fallbackRows = [];
  if (restoreInfo) fallbackRows.push(
    `<span class="badge restoring" style="font-size:9px">🔄 RESTORING · ${_attr(restoreInfo.elapsed_label)}</span>`);
  if (isIsolated && !coveredByDec.has('isolate_vm')) {
    const s = states.find(s => s.type === 'isolated');
    fallbackRows.push(`<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
      <span class="badge isolated" style="font-size:9px;cursor:default">ISOLATED · ${age(s?.since)}</span>${_scopeNote(s)}${_nicNote(s, vm_name)}${_doorNote(s)}
      <button class="action danger" ${_on('click', 'confirmRelease', vm_name)} style="font-size:9px;padding:2px 7px">↩️ Release</button>
    </div>`);
  }
  if (isBlocked && !coveredByDec.has('block_suspicious_ip')) {
    fallbackRows.push(`<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
        ${blocks.length > 1 ? _blocksSummary(blocks, resource_id) + _manageBtn(blocks, resource_id)
                            : _blockBadge(blocks[0], vm_name) + _blockBtns(blocks[0], vm_name)}
      </div>`);
  }
  if (isIsolated && isBlocked) fallbackRows.push(
    `<button class="action danger" ${_on('click', 'confirmReset', vm_name)} style="font-size:9px;padding:2px 7px">⟳ Reset</button>`);

  const isClean = !isIsolated && !isBlocked && !restoreInfo && !myEscs.length;

  const globalDefault = _state?.autonomy_default || 'human_only';
  const autonomyMode  = (_state?.autonomy_modes || {})[vm_name] || globalDefault;
  // The mode is ALWAYS shown (per-VM visibility). At the global default it's discreet
  // (neutral/dim); a per-asset override is highlighted in the posture colour — orange =
  // can act (non_disruptive), blue = observe (human_only) — so exceptions pop out.
  const modeDeviates = autonomyMode !== globalDefault;
  const modeIsAct    = autonomyMode === 'non_disruptive';
  // Full-text badge on its own row (below the name) — discreet at the global default,
  // tinted (orange=act, blue=observe) on a per-asset override. Click → capability popover.
  const modeTxt   = `${modeIsAct ? '⚡' : '👁'} ${modeIsAct ? 'NON-DISRUPTIVE' : 'HUMAN-ONLY'}`;
  const _defLabel = globalDefault === 'non_disruptive' ? 'non-disruptive' : 'human-only';
  const _modeBase = 'font-size:8px;font-weight:700;padding:1px 5px;border-radius:3px;letter-spacing:.5px;flex-shrink:0;cursor:pointer';
  const _modeClick = `${_on('click', 'capability', autonomyMode)}`;
  // Configured autonomous but held in human-only by its readiness (L6 gate): say why,
  // and one click opens the activation screen.
  const modeHold = (_state?.autonomy_holds || {})[vm_name];
  const holdChip = modeHold
    ? `<span ${_on('click', 'openActivation', vm_name)} title="${_attr(`Configured ${modeHold.configured}, held in human-only: ${modeHold.message}. Click to review and turn on.`)}" style="${_modeBase};background:color-mix(in srgb,var(--orange) 12%,transparent);color:var(--orange);border:1px dashed color-mix(in srgb,var(--orange) 45%,transparent)">⏸ ${modeHold.reason === 'not_checked' ? 'CHECKING' : modeHold.reason === 'not_ready' ? 'NOT READY' : 'CONFIRM'}</span>`
    : '';
  const modeBadge = holdChip + (modeHold
    ? `<span ${_modeClick} title="Held in human-only until its readiness allows (configured: ${_attr(modeHold.configured)}) · click for capability" style="${_modeBase};background:transparent;color:var(--dim);border:1px solid var(--border)">${modeTxt}</span>`
    : !modeDeviates
    ? `<span ${_modeClick} title="Autonomy — matches global default · click for capability" style="${_modeBase};background:transparent;color:var(--dim);border:1px solid var(--border)">${modeTxt}</span>`
    : modeIsAct
    ? `<span ${_modeClick} title="Override — acts autonomously (global default: ${_defLabel}) · click for capability" style="${_modeBase};background:color-mix(in srgb,var(--orange) 16%,transparent);color:var(--orange);border:1px solid color-mix(in srgb,var(--orange) 35%,transparent)">${modeTxt}</span>`
    : `<span ${_modeClick} title="Override — recommend only (global default: ${_defLabel}) · click for capability" style="${_modeBase};background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue);border:1px solid color-mix(in srgb,var(--blue) 30%,transparent)">${modeTxt}</span>`);

  const modeSelector = isExpanded
    ? `<div style="display:flex;align-items:center;gap:6px;margin-top:6px">
        <span style="font-size:9px;color:var(--dim);font-weight:600;letter-spacing:.5px">MODE</span>
        <select ${_on('change', 'modeChange', vm_name)} ${_on('click', 'stop')}${_state?.read_only ? ' disabled title="Observe-only (read-only credentials): human-only is locked"' : ''}
          style="font-size:9px;background:var(--bg2);border:1px solid var(--border);color:var(--text);padding:2px 5px;border-radius:3px;cursor:pointer">
          <option value="human_only"${autonomyMode === 'human_only' ? ' selected' : ''}>human-only (recommend)</option>
          <option value="non_disruptive"${autonomyMode === 'non_disruptive' ? ' selected' : ''}>non-disruptive (execute)</option>
        </select>
      </div>`
    : '';

  // Backup section — from audit data (refreshed every 5 min or on user click)
  const backupCheck = (auditEntry?.checks || []).find(c => c.action === 'restore_from_backup');
  const backupMsg = backupCheck?.message || '';
  // Extract "latest Xh ago" from message like "Vault 'rsv-annatar': 5 point(s), latest 2h ago"
  const bMatch = backupMsg.match(/(\d+)\s*point[^,]*,\s*latest\s+(.+)/);
  const backupFix = backupCheck?.fix ? `\nFix: ${backupCheck.fix}` : '';
  const backupSummary = bMatch
    ? `<span style="color:var(--green)">${_attr(bMatch[1])} RP</span> <span style="color:var(--dim)">· last ${_attr(bMatch[2])}</span>`
    : backupCheck
      ? `<span style="color:var(--dim);font-size:9px" title="${_attr(backupMsg + backupFix)}">${_attr(backupMsg || 'checking…')}</span>`
      : `<span style="color:var(--dim)">—</span>`;

  const activeJob = (_state?.active_jobs || []).find(
    j => j.resource_id === resource_id || j.resource_id?.split('/').pop() === vm_name);
  const snapshotInProgress = activeJob?.type === 'snapshot' && activeJob?.status === 'InProgress';
  const snapshotFailed     = activeJob?.type === 'snapshot' && activeJob?.status === 'Failed';
  // Stale (commit c514596): InProgress >24h with no terminal Azure state → zombie job.
  // Yellow, distinct from Failed (red) — it may still be running, just unverified.
  const snapshotStale      = activeJob?.type === 'snapshot' && activeJob?.status === 'Stale';
  // Escalade snapshot pending : bouton déjà dans la carte d'escalade — ne pas doubler dans BACKUP
  // ATT1: nor while an unattributed snapshot's card waits on this tile — the detection does not name
  // this VM, its card has no Snapshot: the tile's own button would take it back.
  const hasSnapshotEsc = myEscs.some(e => _isSnapshotPending(e) || _looseSnapshot(e));
  const snapshotBtn = snapshotInProgress
    ? `<button class="action" disabled style="margin-left:auto;font-size:9px;padding:2px 7px;opacity:.5;cursor:default">⏳ Snapshot…</button>`
    : snapshotStale
      ? `<button class="action" ${_on('click', 'doSnapshot', vm_name)} style="margin-left:auto;font-size:9px;padding:2px 7px;background:color-mix(in srgb,var(--yellow) 20%,transparent);color:var(--yellow);border-color:var(--yellow)" title="Snapshot job stale — InProgress >24h with no terminal state. Re-check Azure or relaunch.">⏱ Stale</button>`
    : snapshotFailed
      ? `<button class="action" ${_on('click', 'doSnapshot', vm_name)} style="margin-left:auto;font-size:9px;padding:2px 7px;background:color-mix(in srgb,var(--red) 20%,transparent);color:var(--red);border-color:var(--red)" title="${_attr(activeJob?.error || 'Snapshot failed')}">✗ Retry</button>`
      : hasSnapshotEsc
        ? ''
        : `<button class="action" ${_on('click', 'doSnapshot', vm_name)} style="margin-left:auto;font-size:9px;padding:2px 7px">📸 Snapshot</button>`;

  // Readiness checks (NSG / Backup / Compute / Detection) — shown in any expanded card. During an
  // incident "can Glorfindel act on this VM?" matters more, not less → not gated on isClean.
  const readinessExpanded = auditEntry
    ? `<div style="display:flex;gap:14px;margin-top:6px;flex-wrap:wrap">
        ${ACTION_GROUPS.map(g => {
          const st = _worstStatus(auditEntry.checks, g.actions);
          const [ic, col] = st==='ok' ? ['✓','var(--green)'] : st==='warn' ? ['⚠','var(--orange)']
                          : st==='fail' ? ['✗','var(--red)'] : ['—','var(--dim)'];
          const detail = _groupDetail(auditEntry.checks, g.actions);
          const cursor = detail ? ';cursor:help' : '';
          return `<span style="font-size:11px;color:${col};font-weight:600${cursor}" title="${_attr(`${g.label}: ${st}${detail ? '\n' + detail : ''}`)}">${ic} ${g.label}</span>`;
        }).join('')}
      </div>` : '';

  const backupSection = `<div class="section-group s-recover" style="margin-top:5px">
    <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
      <span style="color:var(--green);font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Backup</span>
      <button ${_on('click', 'refreshAuditVm', vm_name)}
        style="background:none;border:none;color:var(--dim);cursor:pointer;font-size:11px;padding:0 2px;line-height:1" title="Refresh backup info">↺</button>
      <span style="margin-left:2px">${backupSummary}</span>
      ${snapshotBtn}
    </div>
  </div>`;

  // VM ↔ its NSG (from the audit's structured NSG check) — NIC NSG = this VM only,
  // subnet NSG = shared with the subnet.
  // A failed check carries the NICs of a VM without NSG (IPS2): never an NSG line from it.
  const _nsgCheck = (auditEntry?.checks || []).find(c => c.name === 'NSG access');
  const _nsgData = (_nsgCheck && _nsgCheck.status === 'ok' && _nsgCheck.data) || {};
  // Multi-NIC at rest: data.nsgs[] enumerates every NIC's NSG. With >1, show a clickable
  // "N NSGs" chip → same per-NIC modal as the isolation coverage popover. Single NIC keeps
  // the inline one-liner. data.nsg/nsg_scope (primary NIC) is the back-compat fallback.
  const _nsgs = Array.isArray(_nsgData.nsgs) ? _nsgData.nsgs : [];
  let nsgLine = '';
  if (_nsgs.length > 1) {
    const idx = _coverageCache.push({
      vmName: vm_name, type: 'nsg', ip: '',
      placements: _nsgs.map(x => ({ nsg: x.nsg, scope: x.nsg_scope, nic_id: x.nic_id, ips: x.ips })),
    }) - 1;
    const subnetN = _nsgs.filter(x => x.nsg_scope === 'subnet').length;
    nsgLine = `<div style="font-size:9px;color:var(--dim);margin-top:5px;cursor:pointer"
      ${_on('click', 'showCoverageModal', idx)}
      title="Click for the NSG on each NIC">🛡 ${Number(_nsgs.length)} NSGs across NICs${subnetN ? ` · <span style="color:var(--orange)">${subnetN} subnet</span>` : ''} ▸</div>`;
  } else if (_nsgData.nsg) {
    nsgLine = `<div style="font-size:9px;color:var(--dim);margin-top:5px">🛡 NSG <span style="color:var(--text)">${_attr(_nsgData.nsg.split('/').pop())}</span> · <span style="color:${_nsgData.nsg_scope === 'subnet' ? 'var(--orange)' : 'var(--dim)'}">${_nsgData.nsg_scope === 'subnet' ? 'subnet (shared)' : 'NIC (this VM)'}</span></div>`;
  }

  const expandedBody = `
    ${readinessExpanded}
    ${_idBlock(ident)}
    ${nsgLine}
    ${_netBlock(net)}
    ${modeSelector}
    ${fallbackRows.length ? `<div style="display:flex;flex-direction:column;gap:5px;margin-top:6px">${fallbackRows.join('')}</div>` : ''}
    ${decisionHtml || ''}
    ${myEscs.length ? `<div class="vm-escalations" style="margin:8px 0 0;padding:8px 0 0;border-top:1px solid var(--border)">
      ${_groupEscs(myEscs).map(_renderEscGroup).join('')}
    </div>` : ''}
    ${myDetEscs.length ? `<div class="vm-escalations" style="margin:8px 0 0;padding:8px 0 0;border-top:1px solid var(--border)">
      ${_groupEscs(myDetEscs).map(_renderEscGroup).join('')}
    </div>` : ''}
    ${backupSection}`;

  // Compact clean: backup age + snapshot button (always visible without expanding)
  const backupCompact = bMatch
    ? `<span style="font-size:9px;color:var(--green)">${_attr(bMatch[1])} RP</span><span style="font-size:9px;color:var(--dim)"> · ${_attr(bMatch[2])}</span>`
    : `<span style="font-size:9px;color:var(--dim)">—</span>`;

  const compactSnapshotBtn = snapshotInProgress
    ? `<button class="action" disabled style="margin-left:auto;font-size:9px;padding:1px 6px;opacity:.5;cursor:default">⏳ Snapshot…</button>`
    : snapshotStale
      ? `<button class="action" ${_on('click', 'doSnapshot', vm_name)} style="margin-left:auto;font-size:9px;padding:1px 6px;background:color-mix(in srgb,var(--yellow) 20%,transparent);color:var(--yellow);border-color:var(--yellow)" title="Snapshot job stale — InProgress >24h with no terminal state. Re-check Azure or relaunch.">⏱ Stale</button>`
    : snapshotFailed
      ? `<button class="action" ${_on('click', 'doSnapshot', vm_name)} style="margin-left:auto;font-size:9px;padding:1px 6px;background:color-mix(in srgb,var(--red) 20%,transparent);color:var(--red);border-color:var(--red)" title="${_attr(activeJob?.error || 'Snapshot failed')}">✗ Retry</button>`
      : hasSnapshotEsc
        ? ''
        : `<button class="action" ${_on('click', 'doSnapshot', vm_name)} style="margin-left:auto;font-size:9px;padding:1px 6px">📸 Snapshot</button>`;

  const compactBody = isClean
    ? `<div style="margin-top:5px;display:flex;align-items:center;gap:6px">
        ${backupCompact}
        ${escBadge}
        ${compactSnapshotBtn}
      </div>`
    : `<div class="node-asset-states" style="margin-top:6px">${stateBadges}</div>`;

  return `<div class="node-asset ${stateClass} ${isExpanded ? 'expanded' : ''}${_exclusionOf(vm_name) ? ' excluded' : ''}"
    id="asset-${_attr(vm_name)}"
    draggable="true"
    ${_on('dragstart', 'dragVm', vm_name)}
    ${_on('dragend', 'dragEnd')}
    ${_on('dragover', 'dragOver')}
    ${_on('dragleave', 'dragLeave')}
    ${_on('drop', 'dropOn', slotIdx)}>
    <div class="node-asset-header" ${_on('click', 'toggleAsset', vm_name)}>
      <div style="display:flex;align-items:center;gap:6px">
        ${dot}
        <span class="node-asset-name" title="${_attr(_identityTip(ident))}">${_attr(vm_name)}</span>
        <span style="color:var(--dim);font-size:9px;margin-left:auto;flex-shrink:0">${isExpanded ? '▾' : '▸'}</span>
      </div>
      ${(offlineBadge || unmonitoredBadge || staleBadge || modeBadge || (readiness && !isExpanded)) ? `
      <div style="display:flex;align-items:center;gap:6px;margin-top:5px;flex-wrap:wrap">
        ${offlineBadge}
        ${unmonitoredBadge}
        ${staleBadge}
        ${_exclusionChip(vm_name)}
        ${modeBadge}
        ${_bareChip(net)}
        ${readiness && !isExpanded ? `<span style="color:var(--dim);font-size:9px;margin-left:auto">${readiness}</span>` : ''}
      </div>` : ''}
      ${_addrLine(net)}
      ${_exclusionBand(vm_name)}
      ${_handledLines(resource_id, vm_name)}
    </div>
    ${isExpanded ? expandedBody : compactBody}
  </div>`;
}

// ── Topology edge drawing ──────────────────────────────────────────────────────

// Is a VM actually protected by the RSV (vs merely discovered)? From the audit's
// backup check — data.protected when present, else status != fail. null = unknown.
// Is this asset actually protected? Ground truth = the vault inventory (_backupItems),
// the same source the RECOVER node and the "unprotected" count use. Returns true (in the
// vault), false (loaded, not in vault), or null (inventory not loaded yet → unknown).
// Per-VM audit was unreliable here: an AKS node errors (BMSUserErrorDataSourceObjectNotFound)
// and its card name flips, so an audit miss read as "unknown" → spurious recover link.
function _vmProtected(vmName) {
  const items = (_backupItems && Array.isArray(_backupItems.items)) ? _backupItems.items : null;
  if (!items) return null;
  const n = (vmName || '').toLowerCase();
  return items.some(it =>
    ((it.name || (it.resource_id || '').split('/').pop() || '').toLowerCase()) === n);
}

function _drawTopologyEdges() {
  const svg   = document.getElementById('topo-svg');
  const graph = document.getElementById('topo-graph');
  if (!svg || !graph) return;
  // In the content's coordinates, not the screen's: the svg scrolls with the cards, so a point
  // is where the screen shows it plus how far the map is scrolled. Drawn on the screen's, every
  // refresh made while scrolled put each edge `scrollTop` pixels above its card (TOPO1 #927).
  const base = graph.getBoundingClientRect();
  const ox = base.left + graph.clientLeft - graph.scrollLeft;
  const oy = base.top  + graph.clientTop  - graph.scrollTop;

  function pt(el, side) {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const x = r.left - ox + r.width / 2;
    return {
      x,
      top:    r.top    - oy,
      bottom: r.bottom - oy,
      left:   r.left   - ox,
      right:  r.right  - ox,
      width:  r.width,
    };
  }

  function bezier(x1, y1, x2, y2, color, dash = '', width = 2.5, opacity = 0.75, cls = '') {
    const cy = (y1 + y2) / 2;
    return `<path d="M${x1|0},${y1|0} C${x1|0},${cy|0} ${x2|0},${cy|0} ${x2|0},${y2|0}"
      fill="none" stroke="${color}" stroke-width="${width}" opacity="${opacity}"
      stroke-linecap="round"
      ${dash ? `stroke-dasharray="${dash}"` : ''}${cls ? ` class="${cls}"` : ''}/>`;
  }

  const rules           = _cfgData?.detection?.rules    || [];
  const detectBackends  = _cfgData?.monitoring_backends || [];
  const recoverBackends = (_cfgData?.assets || []).filter(a => a.type === 'azure_backup_vault');
  const { resources = [], escalations = [], restores = [] } = _state;
  const restoring = new Set(restores.map(r => r.vm_name));
  const isIsolated = resources.some(r => r.states?.some(s => s.type === 'isolated'));
  const isBlocked  = resources.some(r => r.states?.some(s => s.type === 'blocked'));

  const agent = pt(document.getElementById('node-agent'));
  // The layer outlives a render now: nothing to draw from, the last edges go with it.
  if (!agent) { svg.innerHTML = ''; return; }

  const lines = [`<defs>
    <filter id="glow-r"><feGaussianBlur stdDeviation="2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <filter id="glow-o"><feGaussianBlur stdDeviation="2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>`];

  // Agent → DETECT backends (always blue — identity color)
  detectBackends.forEach(b => {
    const nb = pt(document.getElementById(`nb-${b.name}`));
    if (!nb) return;
    lines.push(bezier(agent.x, agent.bottom, nb.x, nb.top, 'var(--blue)'));
  });

  // Agent → PROTECT (always orange — identity color, state shown in node)
  const nbNsg = pt(document.getElementById('module-protect'));
  if (nbNsg) {
    lines.push(bezier(agent.x, agent.bottom, nbNsg.x, nbNsg.top, 'var(--orange)'));
  }

  // Agent → RECOVER backends (always green — identity color, state shown in node)
  recoverBackends.forEach(b => {
    const nb = pt(document.getElementById(`nb-${b.name}`));
    if (!nb) return;
    lines.push(bezier(agent.x, agent.bottom, nb.x, nb.top, 'var(--green)'));
  });

  // Structural edges: modules → assets (always visible, dim)
  const discovered = _state?.discovered_assets || [];
  const assetEls = [...document.querySelectorAll('[id^="asset-"]')];

  assetEls.forEach(el => {
    const vmName  = el.id.replace('asset-', '');
    const asset   = pt(el);
    if (!asset) return;
    // An NSG tile: PROTECT only — no backend detects it, no vault restores it.
    if (el.dataset.kind === 'nsg') {
      if (nbNsg) lines.push(bezier(nbNsg.x, nbNsg.bottom, asset.x, asset.top, 'var(--orange)', '', 1.5, 0.4));
      return;
    }
    // AL1c: a group, the control plane, the identities — detected, never protected nor restored.
    if (el.dataset.kind) {
      const det = detectBackends.length ? pt(document.getElementById(`nb-${detectBackends[0].name}`)) : null;
      if (det) lines.push(bezier(det.x, det.bottom, asset.x, asset.top, 'var(--blue)', '', 1.5, 0.3));
      return;
    }

    // DETECT → VM  (via the monitoring backend that discovered it)
    const disc = discovered.find(d => d.name === vmName);
    const detNb = disc
      ? pt(document.getElementById(`nb-${disc.monitoring_backend}`))
      : detectBackends.length ? pt(document.getElementById(`nb-${detectBackends[0].name}`)) : null;
    if (detNb) lines.push(bezier(detNb.x, detNb.bottom, asset.x, asset.top,
      'var(--blue)', '', 1.5, 0.3));

    // PROTECT → VM: pale, or the action done in its colour, solid (LEG1) — isolated red, blocked orange,
    // both side by side.
    if (nbNsg) {
      const vmRes = resources.find(r => r.vm_name === vmName || r.resource_id.endsWith(vmName));
      const vmIso = vmRes?.states?.some(s => s.type === 'isolated');
      const vmBlk = vmRes?.states?.some(s => s.type === 'blocked');
      if (vmBlk) lines.push(bezier(nbNsg.x, nbNsg.bottom, asset.x - (vmIso ? 6 : 0), asset.top, _mark('block').color, '', 2, 0.9));
      if (vmIso) lines.push(bezier(nbNsg.x, nbNsg.bottom, asset.x + (vmBlk ? 6 : 0), asset.top, _mark('isolate').color, '', 2, 0.9));
      if (!vmIso && !vmBlk) lines.push(bezier(nbNsg.x, nbNsg.bottom, asset.x, asset.top, 'var(--orange)', '', 1.5, 0.2));
    }
    // RECOVER → VM, a restore in course: solid green (LEG1).
    if (restoring.has(vmName) && recoverBackends.length) {
      const nb = pt(document.getElementById(`nb-${recoverBackends[0].name}`));
      if (nb) lines.push(bezier(nb.x, nb.bottom, asset.x + _RESTORING_DX, asset.top, _mark('restore').color, '', 2, 0.9));
    }

    // RECOVER → VM — only when the asset is CONFIRMED in the vault inventory. Unknown
    // (inventory not loaded) or absent → no link, so we never imply a backup relationship
    // we haven't confirmed (e.g. AKS nodes, which aren't vault-protected items).
    if (_vmProtected(vmName) === true) recoverBackends.forEach(b => {
      const nb = pt(document.getElementById(`nb-${b.name}`));
      if (nb) lines.push(bezier(nb.x, nb.bottom, asset.x, asset.top,
        'var(--green)', '', 1.5, 0.4));
    });
  });

  // A card waiting for a human: dotted and flowing toward its tile, in the colour of what it asks, from
  // the module that would do it (LEG1) — a detection to judge from DETECT, never from PROTECT. One line
  // per tile and kind, however many cards; beside the solid line of a state done, never over it.
  const drawn = new Set();
  escalations.forEach(e => {
    const edge = _cardEdge(e);
    if (!edge) return;
    const vm    = _ownTile(e) || e.resource_id.split('/').pop();
    const asset = pt(document.getElementById(`asset-${vm}`));
    if (!asset || drawn.has(`${vm}|${edge.key}`)) return;
    drawn.add(`${vm}|${edge.key}`);
    const nb = edge.from === 'recover' ? pt(document.getElementById(`nb-${recoverBackends[0]?.name}`))
      : edge.from === 'detect' ? pt(document.getElementById(`nb-${detectBackends[0]?.name}`))
      : nbNsg;
    const own = !!_ownTile(e);
    if (nb) lines.push(bezier(nb.x, nb.bottom, asset.x + _waitDx(edge.key), asset.top, edge.color, '', own ? 3 : 2.5, 0.9, 'edge-wait'));
  });

  svg.innerHTML = lines.join('\n');
}

async function doApproveRule(proposalId, escId) {
  try {
    const r = await _post(`/api/action/approve-rule/${_seg(proposalId)}`);
    const d = await r.json();
    // P1: an approved rule goes to the client's layer, never into the shipped base.
    if (d.ok && d.rule_bound === false) toast(`⚠ Rule '${d.rule_name}' written to ${d.rules_file || "the client's layer"} but not bound (${d.rule_unbound_reason || 'no backend'}): it applies to no discovered VM — bind it there (monitoring_backends, assets: [auto])`, true);
    else if (d.ok) toast(`✓ Rule '${d.rule_name}' ${d.rule_write === 'same' ? 'already in' : d.rule_write === 'replaced' ? 'replaced in' : 'added to'} the client's layer${d.rules_file ? ' (' + d.rules_file + ')' : ''} — restart watch to activate`);
    else toast('Error: ' + (d.error || 'unknown'), true);
    // Always ack the escalation — rule may already be approved via CLI
    await doAck(escId);
    refreshState();
  } catch (e) { toast('Error: ' + e.message, true); }
}

async function doRejectRule(proposalId, escId) {
  try {
    const r = await _post(`/api/action/reject-rule/${_seg(proposalId)}`);
    const d = await r.json();
    if (d.ok) toast(`✗ Rule '${d.rule_name}' rejected`);
    // Always ack the escalation — rule may already be rejected via CLI
    await doAck(escId);
    refreshState();
  } catch (e) { toast('Error: ' + e.message, true); }
}

// ── Actions ────────────────────────────────────────────────────────────────────

function confirmRelease(vmName) {
  openModal(
    'Release isolation — ' + vmName,
    'Remove the NSG isolation rule. IP blocks (if any) remain active.',
    `glorfindel release ${vmName} --yes`,
    '↩️ Release',
    'danger',
    () => doRelease(vmName),
  );
}

async function doRelease(vmName) {
  if (_guardReadOnly()) return;
  toast('↩️ Releasing isolation on ' + vmName + '…');
  _pendingActions.add(vmName); renderInfra();
  try {
    const r = await _post(`/api/action/release/${_seg(vmName)}`);
    const d = await _settled(await r.json());
    if (d.ok) toast('✓ Isolation released — ' + vmName + ' is back online');
    else if (d.capability_gap) toast('✗ ' + d.error, 8000);
    else toast('✗ Release failed: ' + (d.error || _cliTail(d.stdout) || d.stderr || '?'), 10000);
  } catch (e) { toast('✗ ' + e.message); }
  finally { _pendingActions.delete(vmName); refreshState(); }
}

// A confirmation opened from the blocks' window: a plain modal again (its Cancel, its width).
function _plainModal() {
  document.getElementById('modal-cancel').style.display = '';
  document.querySelector('.modal').classList.remove('wide');
}

// Unblock ONE IP (CON-K): its block alone goes; the VM's other blocks and its isolation stay.
// Its reach said as it is: a block extended to the subnet (`wide`) goes from the subnet's NSG,
// every VM there reachable from the IP again — never said « on this VM ».
function confirmUnblockIp(vmName, ip, wide, nsg) {
  _plainModal();
  openModal(
    wide ? `Unblock ${ip} subnet-wide — ${nsg || vmName}` : `Unblock ${ip} — ${vmName}`,
    wide ? `Remove the subnet-wide block of ${ip} (NSG ${nsg || '?'}): every VM on the subnet is reachable from ${ip} again.`
         : `Remove the block of ${ip} on this VM. Its other blocks, and its isolation if any, stay.`,
    `glorfindel unblock --yes -- ${ip} ${vmName}`,
    '↩️ Unblock',
    'danger',
    () => doUnblockIp(vmName, ip),
  );
}

async function doUnblockIp(vmName, ip) {
  if (_guardReadOnly()) return;
  toast(`↩️ Unblocking ${ip} on ${vmName}…`);
  _pendingActions.add(vmName); renderInfra();
  try {
    const r = await _post(`/api/action/unblock/${_seg(vmName)}?${new URLSearchParams({ ip })}`);
    const d = await _settled(await r.json());
    if (d.ok && d.not_found) toast(`? No block rule of ${ip} found on ${vmName} — already removed?`, 8000);
    else if (d.ok) toast(`✓ ${ip} unblocked on ${vmName}`);
    else if (d.capability_gap) toast('✗ ' + d.error, 8000);
    else toast(`✗ Unblock of ${ip} failed: ` + (d.error || _cliTail(d.stdout) || d.stderr || '?'), 10000);
  } catch (e) { toast('✗ ' + e.message); }
  finally { _pendingActions.delete(vmName); refreshState(); }
}

// Promote ONE VM-scoped block, the row's, to the whole subnet (operator decision).
function confirmExtendSubnet(vmName, ip) {
  _plainModal();
  openModal(
    `Extend the block of ${ip} to the subnet — ${vmName}`,
    `This blocks ${ip} for EVERY VM on the subnet (and future ones), replacing the `
      + 'VM-scoped rule with one subnet-wide rule. The subnet rule is placed before the '
      + 'VM rule is removed — no protection gap.',
    '',
    '⚠ Extend to subnet',
    'danger',
    () => doBlockPromote(vmName, ip),
  );
}

async function doBlockPromote(vmName, ip) {
  if (_guardReadOnly()) return;
  toast(`▶ Extending the block of ${ip} to the subnet…`);
  try {
    const r = await _post(`/api/action/block-promote/${_seg(vmName)}?${new URLSearchParams({ ip })}`);
    const d = await _settled(await r.json());
    if (d.permission_denied) { toast('✗ Cannot execute: read-only credentials'); return; }
    if (d.capability_gap) { toast('✗ ' + d.error, 8000); return; }
    if (d.error) { toast('✗ ' + d.error, 6000); return; }
    // « The whole subnet » only when the outcome says the subnet rule holds whole: a NIC on another
    // subnet, a rule kept, an allow before the deny are said, by name (CON-K).
    if (d.whole === true) toast(`✓ Block of ${d.ip} extended to the whole subnet`);
    else _showPromotionSaid(vmName, d);
    refreshState();
  } catch (e) { toast('✗ ' + e.message); }
}

function _showPromotionSaid(vmName, d) {
  const said = Array.isArray(d.said) && d.said.length ? d.said : ['The outcome could not be read: check the subnet NSG.'];
  document.getElementById('modal').dataset.owner = '';
  // Never told short of the subnet: other ports still reachable (exposure) leave the subnet covered.
  document.getElementById('modal-title').textContent = `⚠ Block of ${d.ip} extended — what it leaves out`;
  document.getElementById('modal-body').innerHTML =
    `<div style="margin-bottom:6px">${_attr(vmName)}: the subnet rule is in place; what it leaves out:</div>`
    + said.map(x => `<div style="color:var(--orange);margin:4px 0 4px 8px">• ${_attr(x)}</div>`).join('');
  document.getElementById('modal-cmd').style.display = 'none';
  document.getElementById('modal-cancel').style.display = 'none';
  const btn = document.getElementById('modal-confirm');
  btn.textContent = 'Close'; btn.className = 'action';
  btn.onclick = () => { closeModal(); document.getElementById('modal-cancel').style.display = ''; };
  document.getElementById('modal').classList.add('open');
}

// Every block of a VM, newest first, filterable, each row with its own buttons (decision A of
// 03/11). A snapshot of the state when opened: a row's button opens its confirmation in its place.
function showBlocks(resourceId) {
  const want = String(resourceId || '').toLowerCase();
  const r = (_state?.resources || []).find(x => String(x.resource_id || '').toLowerCase() === want);
  const vmName = r?.vm_name || want.split('/').pop();
  const bs = _blocksOf(r?.states);
  document.getElementById('modal').dataset.owner = '';
  document.getElementById('modal-title').textContent = `Blocks — ${vmName}`;
  document.getElementById('modal-cmd').style.display = 'none';
  document.getElementById('modal-cancel').style.display = 'none';
  const body = document.getElementById('modal-body');
  body.innerHTML = `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap">
      <span>${Number(bs.length)} blocked IP${bs.length === 1 ? '' : 's'}, newest first</span>
      <input id="blocks-filter" type="search" placeholder="filter: IP, NSG…" aria-label="Filter the blocks"
        style="margin-left:auto;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:3px 7px;font:inherit"
        ${_on('input', 'filterBlocks')}>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:11px">
      <thead><tr style="text-align:left;color:var(--dim)"><th>IP</th><th>since</th><th>where</th><th></th></tr></thead>
      <tbody>${bs.map(s => `<tr data-filter="${_attr(`${s.ip} ${s.nsg || ''} ${s.nsg_scope || ''}`.toLowerCase())}" style="border-top:1px solid var(--border)">
        <td style="padding:5px 6px 5px 0;color:var(--text)">${_attr(s.ip)}</td>
        <td style="padding:5px 6px 5px 0;white-space:nowrap">${age(s.since)}</td>
        <td style="padding:5px 6px 5px 0">${_scopeNote(s)}${_nicNote(s, vmName)}</td>
        <td style="padding:5px 0;text-align:right;white-space:nowrap">${_blockBtns(s, vmName)}</td>
      </tr>`).join('')}</tbody>
    </table>
    <div id="blocks-none" style="display:${bs.length ? 'none' : 'block'};margin-top:6px">${bs.length ? 'Nothing matches.' : 'No active block on this VM.'}</div>`;
  const btn = document.getElementById('modal-confirm');
  btn.textContent = 'Close'; btn.className = 'action';
  btn.onclick = () => { closeModal(); document.getElementById('modal-cancel').style.display = ''; };
  document.querySelector('.modal').classList.add('wide');
  document.getElementById('modal').classList.add('open');
  _applyReadOnlyGuards(body);
}

function filterBlocks() {
  if (!(_target instanceof HTMLInputElement)) return;
  const q = _target.value.trim().toLowerCase();
  let shown = 0;
  document.querySelectorAll('#modal-body tr[data-filter]').forEach(tr => {
    const hit = !q || tr.dataset.filter.includes(q);
    tr.style.display = hit ? '' : 'none';
    shown += hit ? 1 : 0;
  });
  const none = document.getElementById('blocks-none');
  if (none) none.style.display = shown ? 'none' : 'block';
}

function confirmReset(vmName) {
  openModal(
    'Reset ' + vmName,
    'Remove isolation AND all IP blocks in one operation.',
    `glorfindel revert ${vmName} --yes`,
    '⟳ Reset',
    'danger',
    () => doRevert(vmName),
  );
}

function confirmRevert(vmName) {
  // kept for backward compat (called from escalation cards, bot, etc.)
  confirmReset(vmName);
}

// A restore asks for its moment (SEC4c): the newest recovery point from before the attack
// began. The field is filled with what the server proposes (an exercise's attack_started for
// this VM, else the card's first detection); the points before it are shown, read only; the
// operator confirms, and the restore runs with --before.
let _restoreWindow = 0;     // the restore window's token: another window opened meanwhile wins
async function confirmRestore(vmName, escId) {
  const mine = String(++_restoreWindow);
  const modal = document.getElementById('modal');
  modal.dataset.owner = 'restore-' + mine;
  const title = 'Restore ' + vmName + ' from backup';
  // Ours while open, under our token and our title — a window opened meanwhile by any other
  // path (it sets its own title) is never overwritten.
  const _stillMine = () => modal.dataset.owner === 'restore-' + mine && modal.classList.contains('open')
    && document.getElementById('modal-title').textContent === title;
  document.getElementById('modal-title').textContent = title;
  const body = document.getElementById('modal-body');
  body.innerHTML = '<div style="color:var(--dim)">Reading what the restore would take (nothing is changed)…</div>';
  document.getElementById('modal-cmd').style.display = 'none';
  document.getElementById('modal-cancel').style.display = '';
  const btn = document.getElementById('modal-confirm');
  btn.style.display = '';
  btn.textContent = '🔄 Restore';
  btn.className = 'primary';
  btn.disabled = true;
  document.getElementById('modal').classList.add('open');
  let d;
  try {
    d = await (await fetch(`/api/restore/plan/${_seg(vmName)}?escalation=${_seg(escId)}`)).json();
  } catch (e) { if (_stillMine()) body.textContent = '✗ ' + e.message; return; }
  // Closed, or another window opened while the plan was read: it is not this one's to fill.
  if (!_stillMine()) return;
  if (d.error && !d.why) { body.textContent = '✗ ' + d.error; return; }
  body.innerHTML = `
    <div style="margin-bottom:6px;color:var(--text)">Restore to the newest recovery point from before…</div>
    <input id="restore-before" type="text" value="${_attr(d.before)}" placeholder="2026-10-29T08:00:00+00:00"
      style="width:100%;font-family:var(--font);background:var(--bg2);color:var(--text);border:1px solid var(--border);padding:4px 6px">
    <div id="restore-why" style="color:var(--dim);font-size:11px;margin-top:4px">${_attr(d.why)}</div>
    <div id="restore-warning" style="color:var(--orange);font-size:11px;margin-top:4px">${d.warning ? '⚠ ' + _attr(d.warning) : ''}</div>
    <div style="margin-top:6px"><button class="action" ${_on('click', 'restorePoints', vmName, escId)} style="font-size:10px;padding:2px 7px">↺ Points before this moment</button></div>
    <div id="restore-points" style="margin-top:8px;font-size:11px"></div>
    <div style="color:var(--dim);font-size:11px;margin-top:8px">~20 min, the VM offline meanwhile. Glorfindel releases the isolation once the restore is done.</div>`;
  _renderRestorePoints(d);
  btn.disabled = false;
  btn.onclick = () => {
    const before = document.getElementById('restore-before').value.trim();
    if (!before) { toast('✗ Give the moment to restore before'); return; }
    closeModal();
    doRestore(vmName, escId, before);
  };
}

function _renderRestorePoints(d) {
  const el = document.getElementById('restore-points');
  if (!el) return;
  if (d.error) { el.innerHTML = `<div style="color:var(--red)">✗ ${_attr(d.error)}</div>`; return; }
  if (d.points_error) { el.innerHTML = `<div style="color:var(--orange)">Recovery points unreadable: ${_attr(d.points_error)}</div>`; return; }
  const points = Array.isArray(d.points) ? d.points : [];
  if (!d.moment) { el.innerHTML = '<div style="color:var(--dim)">Give a moment to see the points before it.</div>'; return; }
  if (!points.length) { el.innerHTML = `<div style="color:var(--red)">No recovery point before ${_attr(d.moment)}: the restore would be refused.</div>`; return; }
  el.innerHTML = `<div style="color:var(--dim);margin-bottom:3px">Recovery points before ${_attr(d.moment)} (read only):</div>`
    + points.slice(0, 8).map((p, i) => `<div style="color:${i === 0 ? 'var(--green)' : 'var(--text)'}">${_attr(p.time)}${p.vault_tier ? ' · vault tier' : ''}${p.during_incident ? ' · <span style="color:var(--orange)">taken during the incident</span>' : ''}${i === 0 ? ' ← restored' : ''}</div>`).join('');
  const w = document.getElementById('restore-warning');
  if (w) w.textContent = d.warning ? '⚠ ' + d.warning : '';
}

async function restorePoints(vmName, escId) {
  const input = document.getElementById('restore-before');
  if (!(input instanceof HTMLInputElement)) return;
  const el = document.getElementById('restore-points');
  if (el) el.textContent = 'Reading…';
  try {
    const d = await (await fetch(`/api/restore/plan/${_seg(vmName)}?escalation=${_seg(escId)}&before=${encodeURIComponent(input.value.trim())}`)).json();
    _renderRestorePoints(d);
  } catch (e) { if (el) el.textContent = '✗ ' + e.message; }
}

function confirmAck(escId) {
  openModal(
    'Acknowledge escalation',
    'Mark this escalation as resolved. No action will be taken on Azure.',
    `glorfindel ack ${escId.slice(0, 8)}`,
    '✓ Acknowledge',
    'action',
    () => doAck(escId),
  );
}

async function doRevert(vmName) {
  if (_guardReadOnly()) return;
  toast('↩️ Reverting ' + vmName + '…');
  _pendingActions.add(vmName); renderInfra();
  try {
    const r = await _post(`/api/action/revert/${_seg(vmName)}`);
    const d = await _settled(await r.json());
    if (d.ok) toast('✓ Revert complete — ' + vmName + ' is clean');
    else if (d.capability_gap) toast('✗ ' + d.error, 8000);
    else toast('✗ Revert failed: ' + (d.error || _cliTail(d.stdout) || d.stderr || '?'), 10000);
  } catch (e) { toast('✗ ' + e.message); }
  finally { _pendingActions.delete(vmName); refreshState(); }
}

async function doSnapshot(vmName) {
  if (_guardReadOnly()) return;
  toast('📸 Snapshot started for ' + vmName + ' — check RSV for job status');
  try {
    const r = await _post(`/api/action/snapshot/${_seg(vmName)}`);
    const d = await _settled(await r.json());
    if (d.error) toast('✗ Snapshot failed: ' + d.error);
    else refreshState();  // triggers re-render with snapshotInProgress badge
  } catch (e) { toast('✗ ' + e.message); }
}

async function refreshAuditVm(vmName) {
  toast('↺ Refreshing backup info…');
  try {
    const r = await fetch(`/api/audit/${_seg(vmName)}`);
    const d = await r.json();
    if (d.error) { toast('✗ ' + d.error); return; }
    if (!_auditData) _auditData = { audits: [] };
    const idx = (_auditData.audits || []).findIndex(
      a => a.resource_id === d.resource_id || a.asset_name === vmName);
    if (idx >= 0) _auditData.audits[idx] = d;
    else { _auditData.audits = _auditData.audits || []; _auditData.audits.push(d); }
    renderInfra();
    toast('✓ Backup info updated');
  } catch (e) { toast('✗ ' + e.message); }
}

async function doRestore(vmName, escId, before) {
  if (_guardReadOnly()) return;
  try {
    // The card's restore (SEC1): the server checks the card — never an anchored one — and
    // the moment (SEC4c). A refusal of the command itself comes back on the card.
    const d = await (await _post(`/api/action/restore/${_seg(vmName)}`, { escalation: escId, before })).json();
    if (d.error) { toast('✗ Restore refused: ' + d.error, 8000); return; }
    toast('🔄 Restore requested for ' + vmName + ' before ' + d.before + ' — a refusal shows on the card', 8000);
  } catch (e) {
    toast('✗ ' + e.message);
  }
}

// A card's verdict is given in TO JUDGE: highlight it there. A card older than TO JUDGE's
// 7 days is judged from the CLI.
function focusJudge(escId) {
  const el = document.getElementById('judge-' + escId);
  if (!el) { toast(`Not in TO JUDGE (older than 7 days?) — glorfindel verdict ${escId} right|wrong|unsure`); return; }
  document.querySelectorAll('.judge-item.focus').forEach(x => x.classList.remove('focus'));
  el.classList.add('focus');
  el.scrollIntoView({ block: 'nearest' });
}

// ── Observation: what to judge, and the week's count ───────────────────────────
// The operator's daily task during an observation (docs/observation.md): give each
// decision card a verdict. The list holds the last 7 days' cards without one — pending
// or acknowledged —, exercises marked (H-1); the tab's badge counts them, the overview
// shows what `glorfindel report` counts.

let _toJudge = [];

async function refreshObservation() {
  const cards = await _toJudgeNow();
  if (cards) _takeToJudge(cards);
}
// The cards to judge as the server says them now, or null: an error, a refusal, an answer without
// its cards — never the list read before taken for it (JUG3: a batch writes only on a list read again).
async function _toJudgeNow() {
  try {
    const r = await fetch('/api/to-judge?since=7d');
    if (!r.ok) return null;
    const q = await r.json();
    return q && Array.isArray(q.cards) ? q.cards : null;
  } catch (e) { return null; }
}
function _takeToJudge(cards) {
  _toJudge = cards; renderToJudge(); _judgeGroupAgain(); Console.setJudgeCount(cards.length);
}

// VP1c (#920): the card's time carries no time zone, or cannot be read — kept in the list whatever the
// period, never dated by a guess (escalations.to_judge, `time_unreadable`).
const _UNTIMED = 'The card\'s time carries no time zone, or cannot be read: when it fired is not known, and never guessed. It stays here, whatever the period, for you to judge.';
// JUG3: the list redraws every 30 s (refreshObservation): what is being typed stays, and where.
// A note to a card keeps its text; the field the operator is in keeps the focus and the caret — on a
// phone, a field redrawn under the finger closes the keyboard. The batch's note keeps its text by
// itself (_batch.<where>.note): only its focus is put back, never an old text.
function _typed(root) {
  const a = document.activeElement;
  const into = a instanceof HTMLInputElement && a.type !== 'checkbox' && a.id && root.contains(a)
    ? [a.id, a.selectionStart, a.selectionEnd] : null;
  const notes = [...root.querySelectorAll('input[id^="judge-note-"]')].filter(i => i.value).map(i => [i.id, i.value]);
  return { into, notes };
}
function _retype(root, typed) {
  for (const [id, v] of typed.notes) {
    const i = document.getElementById(id);
    if (i && root.contains(i)) i.value = v;
  }
  const i = typed.into && document.getElementById(typed.into[0]);
  if (i && root.contains(i)) {
    i.focus({ preventScroll: true });
    try { i.setSelectionRange(typed.into[1], typed.into[2]); } catch (e) {}
  }
}

function renderToJudge() {
  const list = document.getElementById('judge-list');
  const typed = list ? _typed(list) : null;
  const count = document.getElementById('judge-count');
  if (!list) return;
  if (count) count.textContent = _toJudge.length ? `· ${_toJudge.length}` : '';
  _showMobileTab();                              // the phone's default tab and its badge (MOB4)
  if (!_toJudge.length) {
    list.innerHTML = '<div class="judge-empty">Nothing to judge — every recommendation of the last 7 days has a verdict.</div>' + _batchPanel('list');
    _retype(list, typed);
    return;
  }
  // JUG3: a card checked and gone from the list (judged elsewhere, older than 7 days) is let go.
  for (const id of [..._batch.list.picked]) if (!_toJudge.some(c => c.id === id)) _batch.list.picked.delete(id);
  const allPicked = _batch.list.picked.size === _toJudge.length;
  list.innerHTML = `<label class="judge-all" ${_on('click', 'stop')}><input type="checkbox"${allPicked ? ' checked' : ''} ${_on('change', 'pickAllJudge')}> select all</label>` + _toJudge.map(c => {
    const disruptive = ['isolate_vm', 'block_suspicious_ip'].includes(c.action);
    const pct = c.confidence ? ` ${Math.round(c.confidence * 100)}%` : '';
    // Judge on the evidence: the IP a block targets, the rule that fired, and the model's
    // own explanation — `reason` is often only the gate's wording (a mode hold).
    const p = c.action_params || {};
    const target = p.ip ? ` ${p.ip}${p.port ? ':' + p.port : ''}` : '';
    // A detection-only card recommends nothing: its title says what was detected.
    const what = (c.action ? actionLabelVerb(c.action) : escTitle(c)) + target + pct;
    const why = c.explanation || c.reason || '';
    // AL1c: a card of the control plane or of an identity names what it is about, never a VM it
    // was anchored on; one from before AL1c keeps its ⚓, and says it may not be about that VM
    // (on the first VM online, or on the VM itself: the card cannot tell which).
    const t = _targetOf(c);
    // SLF1 (#929): a detection attributed to no VM says so, with its candidates — never the name of
    // the VM it is filed on.
    const loose = _unattributed(c);
    const vm = t ? (t.kind === 'control_plane' ? _TARGET_KINDS[t.kind]
      : (t.kind === 'identity' ? (t.identity_type || 'identity') : _TARGET_KINDS[t.kind]) + ' ' + (t.name || '?'))
      : loose ? _unattributedTxt(loose)
      : (c.resource_id || '').split('/').pop();
    const anchored = !t && (_isAnchored(c) || !!loose);
    const times = c.occurrences > 1 ? ` · ${Number(c.occurrences)}×` : '';
    const id = _attr(c.id);
    // JUG1: the line opens its card (its details, its verdict); its own note and buttons keep the click.
    return `<div class="judge-item${disruptive ? ' disruptive' : ''}${c.id === _focusCard ? ' focus' : ''}" id="judge-${id}" ${_on('click', 'openJudgeCard', c.id)} title="Open the card">
      <div class="judge-head">
        <label class="judge-pick" ${_on('click', 'stop')} title="Check it, to judge several cards at once"><input type="checkbox" aria-label="Check this card"${_batch.list.picked.has(c.id) ? ' checked' : ''} ${_on('change', 'pickJudge', c.id)}></label>
        <span class="judge-what" style="color:${disruptive ? 'var(--red)' : 'var(--orange)'}">${_attr(what)}</span>
        <span style="flex:1"></span>
        <span class="judge-ts">${c.time_unreadable ? '' : (c.first_seen ? _relTime(c.first_seen) : '')}${times}</span>
      </div>
      ${c.time_unreadable ? `<div class="judge-why judge-untimed" style="-webkit-line-clamp:1;color:var(--yellow)" title="${_attr(_UNTIMED)}">⚠ time unreadable — judge it all the same</div>` : ''}
      <div class="judge-why" style="-webkit-line-clamp:1;color:var(--text)" title="${anchored ? _attr(_DETECTION_ONLY.has(c.escalation_type) ? _FILED_BEFORE : 'The detection does not name this VM: the card is only filed on it') : _attr((t && t.limit) || c.resource_id || '')}">${anchored ? '⚓ ' : (t ? '🎯 ' : '')}${_attr(vm)}${c.rule_name ? ` · rule ${_attr(c.rule_name)}` : ''}${c.ttp ? ` · ${_attr(c.ttp)}` : ''}${c.severity === 'critical' ? ' · <b style="color:var(--red)">critical</b>' : ''}</div>
      ${c.exercise ? `<div class="judge-why" style="-webkit-line-clamp:1;color:var(--blue)" title="An injector's exercise window covered this VM at that time. A window is the injectors' claim: check the run before trusting it.">⚑ exercise${c.exercise_run ? ` · run <a href="/runs/${encodeURIComponent(c.exercise_run)}" ${_on('click', 'stop')}>${_attr(c.exercise_run)}</a> — check the run ▸` : ' — check the run'}</div>` : ''}
      ${_proposedLine(c)}
      ${c.recurrence ? `<div class="judge-why" style="-webkit-line-clamp:1;color:var(--yellow)" title="An earlier card on the same IP: in observation nothing is blocked, so a scanner comes back">↻ same IP seen ${_attr(c.recurrence.previous)}× in 7 days — last ${c.recurrence.last_seen ? _relTime(c.recurrence.last_seen) : ''}${c.recurrence.last_verdict ? ', judged ' + _attr(c.recurrence.last_verdict) : ''}</div>` : ''}
      <div class="judge-why" title="${_attr(why)}">${_attr(why)}</div>
      <div class="judge-actions" ${_on('click', 'stop')}>
        <input id="judge-note-${id}" placeholder="note (optional): why" maxlength="300">
        <button class="action" title="The recommendation was right" ${_on('click', 'judgeCard', c.id, 'right')}>✓ Right</button>
        <button class="action" style="color:var(--red)" title="False positive, or a disproportionate action" ${_on('click', 'judgeCard', c.id, 'wrong')}>✗ Wrong</button>
        <button class="action" style="color:var(--dim)" title="Can't tell with what is known" ${_on('click', 'judgeCard', c.id, 'unsure')}>? Unsure</button>
      </div>
    </div>`;
  }).join('') + _batchPanel('list');
  _retype(list, typed);
  // ?card=<id>: scrolled to once, the first time it is in the list.
  if (_focusCard && document.getElementById('judge-' + _focusCard)) {
    document.getElementById('judge-' + _focusCard).scrollIntoView({ block: 'nearest' });
    _focusCard = null;
  }
}

// ── Judging several cards at once (JUG3, #980, Jonathan 20/11 on a mockup) ─────────────────
// Cards checked in TO JUDGE, or in the window of a group (« ×N »), then one verdict and one note for
// all. Each card gets exactly what its own button gives it — its verdict and the note, then its
// acknowledgement (16/10) —, one card after the other: its own verdict, so the precision, the rate
// of wrong isolations and the memory stay true. Never an action: no « Approve & execute », never a
// verdict proposed (VP1) confirmed in the operator's place. Before anything is written, a summary
// (the count by rule, the note); a card that fails is said, card by card, and the others go on: it
// stays checked, to try again (decisions 1 and 4 of 20/11).
const _VERDICTS = ['right', 'wrong', 'unsure'];
const _batch = {
  list:  { picked: new Set(), ask: null, result: null, note: '', running: '' },
  // The window keeps its cards as they were when opened (cards: an acknowledged card leaves the state)
  // and the verdict each got in it (given): its lines still say what they were, and how judged.
  group: { picked: new Set(), ask: null, result: null, note: '', running: '', ids: [], title: '', cards: {}, given: {} },
};
// One batch at a time for the page: the list's and the group's window never judge at once (the same
// cards could be in both).
function _batchRunning() { return !!(_batch.list.running || _batch.group.running); }
function _batchCard(id) { return _toJudge.find(c => c.id === id) || _escById[id] || null; }
function _batchRule(c) { return String((c && (c.rule_name || c.action || c.escalation_type)) || 'no rule'); }
function _batchLabel(c) {
  if (!c) return '?';
  const t = _targetOf(c);
  const on = t ? (t.name || _TARGET_KINDS[t.kind] || '') : (c.resource_id || '').split('/').pop();
  // The id's first 8 characters (as `glorfindel pending` shows them): two cards of one action on one VM
  // told apart in the outcome.
  return `${c.action ? actionLabelVerb(c.action) : escTitle(c)}${on ? ' — ' + on : ''} · ${String(c.id || '').slice(0, 8)}`;
}
// The group's window only while it is the one open: closed during a batch, another window is never written.
function _batchRender(where) { where === 'group' ? _judgeGroupAgain() : renderToJudge(); }
function _batchPanel(where) {
  const B = _batch[where];
  const parts = [];
  if (B.result) {
    const v = B.result.verdict;
    parts.push(`<div class="judge-batch-result">${B.result.lines.map(l => l.state === 'ok'
      ? `<div class="r-ok">✓ ${_attr(l.label)}: ${_attr(v)}${l.note ? ' · note kept' : ''} · acknowledged</div>`
      : l.state === 'unacked'
      ? `<div class="r-warn">⚠ ${_attr(l.label)}: judged ${_attr(v)}, not acknowledged — ${_attr(l.why)} (Ack it on its tile)</div>`
      : l.state === 'gone'
      ? `<div class="r-warn">↷ ${_attr(l.label)}: left as it was — no longer to judge (judged elsewhere since the summary?)</div>`
      : `<div class="r-bad">✗ ${_attr(l.label)}: not judged — ${_attr(l.why)} (still checked)</div>`).join('')}</div>`);
  }
  if (B.running) parts.push(`<div class="judge-bar" ${_on('click', 'stop')}><b>${_attr(B.running)}</b></div>`);
  else if (B.ask) {
    const n = B.ask.ids.length, byRule = new Map();             // a Map: any rule's name a key (__proto__ too)
    B.ask.ids.forEach(id => { const r = _batchRule(_batchCard(id)); byRule.set(r, (byRule.get(r) || 0) + 1); });
    parts.push(`<div class="judge-confirm" ${_on('click', 'stop')}>
      <div class="judge-confirm-t">Judge ${Number(n)} card${n > 1 ? 's' : ''} ${_attr(B.ask.verdict)}?</div>
      <div>${[...byRule.entries()].map(([r, k]) => `${Number(k)} × ${_attr(r)}`).join(' · ')}</div>
      <div class="judge-confirm-note">${B.ask.note ? 'note: ' + _attr(B.ask.note) : 'no note'}</div>
      <div class="judge-confirm-row"><button class="action" ${_on('click', 'runBatch', where)}>Judge ${Number(n)} ${_attr(B.ask.verdict)}</button><button class="action" ${_on('click', 'cancelBatch', where)}>Cancel</button></div>
    </div>`);
  } else if (B.picked.size) {
    const rules = new Set([...B.picked].map(id => _batchRule(_batchCard(id))));
    parts.push(`<div class="judge-bar" ${_on('click', 'stop')}>
      ${rules.size > 1 ? `<div class="judge-mixed">⚠ ${Number(rules.size)} rules in the selection</div>` : ''}
      <b>${Number(B.picked.size)} selected</b>
      <input id="judge-batch-note-${where}" placeholder="one note for all (optional)" maxlength="300" value="${_attr(B.note)}" ${_on('input', 'batchNote', where)}>
      <button class="action" title="The recommendation was right, for each" ${_on('click', 'askBatch', where, 'right')}>✓ Right</button>
      <button class="action" style="color:var(--red)" title="False positive, or a disproportionate action, for each" ${_on('click', 'askBatch', where, 'wrong')}>✗ Wrong</button>
      <button class="action" style="color:var(--dim)" title="Can't tell with what is known, for each" ${_on('click', 'askBatch', where, 'unsure')}>? Unsure</button>
      <button class="action judge-clear" ${_on('click', 'clearBatch', where)}>clear</button>
    </div>`);
  }
  return parts.join('');
}
// One card, as its own button does it (judgeCard): its verdict and the note, then its acknowledgement —
// each answer read, a refusal said.
async function _judgeOne(id, verdict, note) {
  try {
    const r = await _post(`/api/escalations/${_seg(id)}/verdict`, { verdict, note });
    const d = await r.json().catch(() => ({}));
    if (!r.ok || d.error) return { state: 'fail', why: String(d.error || d.detail || `HTTP ${r.status}`) };
  } catch (e) { return { state: 'fail', why: String(e.message || e) }; }
  try {
    const r = await _post(`/api/action/ack/${_seg(id)}`);
    const d = await r.json().catch(() => ({}));
    if (!r.ok || d.error) return { state: 'unacked', why: String(d.error || d.detail || `HTTP ${r.status}`) };
  } catch (e) { return { state: 'unacked', why: String(e.message || e) }; }
  return { state: 'ok' };
}
async function _runBatch(where) {
  const B = _batch[where];
  if (!B.ask) return;
  if (_batchRunning()) { toast('⏳ A batch is being judged: wait for its end'); return; }
  const { verdict, note, ids } = B.ask;
  B.ask = null;
  // The list read again first: a verdict given since the summary (the bot, another tab) is never
  // written over — the server takes a second verdict, as a card's own button does. Not read again
  // (an error, a refusal): nothing is written, each card said and left checked.
  B.running = 'Reading the list again…';
  _batchRender(where);
  const fresh = await _toJudgeNow();
  if (fresh) _takeToJudge(fresh);
  const lines = [];
  for (const [k, id] of ids.entries()) {                         // one after the other, never at once
    B.running = `Judging ${k + 1} of ${ids.length}…`;
    _batchRender(where);
    const label = _batchLabel(_batchCard(id));
    if (!fresh) { lines.push({ id, label, note: !!note, state: 'fail', why: 'the list could not be read again' }); continue; }
    if (!_toJudge.some(c => c.id === id)) { lines.push({ id, label, note: !!note, state: 'gone' }); continue; }
    lines.push({ id, label, note: !!note, ...(await _judgeOne(id, verdict, note)) });
  }
  B.running = '';
  B.picked = new Set(lines.filter(l => l.state === 'fail').map(l => l.id));   // the failed ones, to try again
  // The note goes with this batch only: kept for a retry of the failed ones, never for the next batch.
  if (!B.picked.size) B.note = '';
  if (B.given) for (const l of lines) if (l.state === 'ok' || l.state === 'unacked') B.given[l.id] = verdict;
  B.result = { verdict, lines };
  const ok = lines.filter(l => l.state === 'ok' || l.state === 'unacked').length;
  toast(ok === lines.length ? `✓ ${ok} card${ok > 1 ? 's' : ''} judged ${verdict}` : `⚠ ${ok} of ${lines.length} judged ${verdict} — see the list`);
  _batchRender(where);
  await refreshState();                 // the verdicts given, on the tiles (and the window's lines)
  await refreshObservation();           // the list, and the window of the group redrawn on it
}

// The window of a group (« to judge ×N » on a tile): its cards to judge, ranged by rule, each with its
// box, « select this rule », « select all » (decision 2 of 20/11); the batch as in the list.
function openJudgeGroup(idsCsv) {
  const B = _batch.group;
  // Its batch running: the window opened again as it is (its group, its progress), never reset under it.
  if (!B.running) {
    // The group's ids, as _renderEscGroup gave them (a group of _groupEscs): only cards the page knows.
    const members = String(idsCsv || '').split(',').filter(id => _escById[id]);
    if (!members.length) return;
    Object.assign(B, { picked: new Set(), ask: null, result: null, note: '', ids: members,
      cards: Object.fromEntries(members.map(id => [id, _batchCard(id)])), given: {} });
    const e = _escById[members[0]];
    B.title = `To judge — ${e.action ? actionLabelVerb(e.action) : _sharedTitle(members.map(id => _escById[id]))} ×${members.length} — ${_tileSaid(e) || String(e.resource_id || '').split('/').pop()}`;
  }
  document.getElementById('modal-title').textContent = B.title;
  document.getElementById('modal').dataset.owner = 'judge-group';
  document.getElementById('modal-cmd').style.display = 'none';
  document.getElementById('modal-cancel').style.display = 'none';
  const btn = document.getElementById('modal-confirm');
  btn.textContent = 'Close';
  btn.className = 'action';
  btn.onclick = () => { closeModal(); document.getElementById('modal-cancel').style.display = ''; };
  _renderJudgeGroup();
  document.querySelector('.modal').classList.add('wide');
  document.getElementById('modal').classList.add('open');
}
// The window of a group, open: redrawn with the list (a card judged elsewhere loses its box). Only
// this window — another one opened since says so by its owner and its title.
function _judgeGroupAgain() {
  const m = document.getElementById('modal');
  if (m && m.classList.contains('open') && m.dataset.owner === 'judge-group'
      && document.getElementById('modal-title').textContent === _batch.group.title) _renderJudgeGroup();
}
function _groupJudgeable() { return _batch.group.ids.filter(id => _toJudge.some(c => c.id === id)); }
function _renderJudgeGroup() {
  const B = _batch.group, body = document.getElementById('modal-body');
  if (!body || !B.ids.length) return;
  const typed = _typed(body);
  const judgeable = _groupJudgeable();
  for (const id of [...B.picked]) if (!judgeable.includes(id)) B.picked.delete(id);
  const byRule = new Map();
  const card = id => _batchCard(id) || B.cards[id] || null;
  B.ids.forEach(id => { const r = _batchRule(card(id)); if (!byRule.has(r)) byRule.set(r, []); byRule.get(r).push(id); });
  const allPicked = judgeable.length > 0 && judgeable.every(id => B.picked.has(id));
  body.innerHTML = `<div class="judge-group">
    ${judgeable.length ? `<label class="judge-all" ${_on('click', 'stop')}><input type="checkbox"${allPicked ? ' checked' : ''} ${_on('change', 'pickGroupAll')}> select all ${Number(judgeable.length)}</label>` : ''}
    ${[...byRule.entries()].map(([rule, ids]) => {
      const open = ids.filter(id => judgeable.includes(id));
      const rulePicked = open.length > 0 && open.every(id => B.picked.has(id));
      return `<div class="judge-rule">${_attr(rule.toUpperCase())} · ${Number(ids.length)}${open.length ? ` <label ${_on('click', 'stop')}><input type="checkbox"${rulePicked ? ' checked' : ''} ${_on('change', 'pickGroupRule', rule)}> select this rule</label>` : ''}</div>
        ${ids.map(id => {
          const c = card(id), can = judgeable.includes(id), given = B.given[id] || (c && c.verdict);
          return `<div class="judge-item judge-group-item${B.picked.has(id) ? ' picked' : ''}">
            <div class="judge-head">${can ? `<label class="judge-pick" ${_on('click', 'stop')}><input type="checkbox" aria-label="Check this card"${B.picked.has(id) ? ' checked' : ''} ${_on('change', 'pickGroup', id)}></label>` : ''}
              <span class="judge-vm">${_attr(_batchLabel(c))}</span>
              <span class="judge-ts">${c && c.first_seen ? _relTime(c.first_seen) : ''}</span></div>
            <div class="judge-why" style="-webkit-line-clamp:1">${can ? 'rule ' + _attr(_batchRule(c)) : given ? 'judged: ' + _attr(given) : 'not in TO JUDGE'}</div>
          </div>`;
        }).join('')}`;
    }).join('')}
    ${_batchPanel('group')}
  </div>`;
  _retype(body, typed);
}

// VP1 (#615): the verdict proposed on an exercise card — the detection the drill of the week expected
// (its rule, on its target, within its delay after T0). Never a verdict given: the card stays to judge
// until the operator confirms it (it becomes their verdict) or refuses it (gone, never proposed again).
// An exercise card without one says why. On the detection only: the decision stays to judge.
// Its Confirm and Refuse sit under the line, never in it: the line is cut at two lines, and a
// proposal of an ordinary length put them below the cut — hidden in the list, at any width (MOB5).
function _proposedLine(c, inModal) {
  if (!c || !c.exercise) return '';
  const p = c.proposed_verdict;
  if (p && typeof p === 'object') {
    const after = Number(p.after_s), within = Number(p.within_s);
    return `<div class="judge-why" style="-webkit-line-clamp:2;color:var(--green)" title="The drill ${_attr(p.drill)} expected this detection: rule ${_attr(p.rule)}, on its target, within ${within} s of the run's T0. Only the detection is compared: confirm only if the action was proportionate too.">⚖ proposed: <b>${_attr(p.verdict)}</b> — the detection the drill ${_attr(p.drill)} expected (rule ${_attr(p.rule)}, its target, ${after} s after T0 ≤ ${within} s); the decision stays yours</div>
      <div class="judge-proposed" ${_on('click', 'stop')}><button class="action" style="color:var(--green)" title="It becomes your verdict" ${inModal ? _on('click', 'confirmProposedFromModal', c.id) : _on('click', 'confirmProposed', c.id)}>✓ Confirm ${_attr(p.verdict)}</button>
      <button class="action" style="color:var(--dim)" title="The proposal is erased, never made again; the card stays to judge" ${inModal ? _on('click', 'refuseProposedFromModal', c.id) : _on('click', 'refuseProposed', c.id)}>✗ Refuse</button></div>`;
  }
  if (c.proposed_refused && typeof c.proposed_refused === 'object') {
    return `<div class="judge-why" style="-webkit-line-clamp:1;color:var(--dim)">⚖ proposed verdict refused — yours to judge</div>`;
  }
  const w = c.proposed_why;
  if (w && typeof w === 'object') {
    return `<div class="judge-why" style="-webkit-line-clamp:1;color:var(--dim)" title="${_attr(w.code)}">⚖ no proposed verdict: ${_attr(w.said)}</div>`;
  }
  return '';
}

async function confirmProposed(escId, noteId) {
  const note = (document.getElementById(noteId || 'judge-note-' + escId)?.value || '').trim();
  try {
    const r = await _post(`/api/escalations/${_seg(escId)}/proposed/confirm`, { note });
    const d = await r.json();
    if (d.error) { toast('✗ ' + d.error); return; }
    await _post(`/api/action/ack/${_seg(escId)}`);      // as any verdict: one click, the card acknowledged
    toast(`✓ Proposed verdict confirmed (${d.verdict})`);
    refreshObservation();
    refreshState();
  } catch (e) {
    toast('✗ ' + e.message);
  }
}

async function refuseProposed(escId) {
  try {
    const r = await _post(`/api/escalations/${_seg(escId)}/proposed/refuse`, {});
    const d = await r.json();
    if (d.error) { toast('✗ ' + d.error); return; }
    toast('Proposed verdict refused — the card stays to judge');
    refreshObservation();
  } catch (e) {
    toast('✗ ' + e.message);
  }
}

async function judgeCard(escId, verdict, noteId) {
  const note = (document.getElementById(noteId || 'judge-note-' + escId)?.value || '').trim();
  try {
    const r = await _post(`/api/escalations/${_seg(escId)}/verdict`, { verdict, note });
    const d = await r.json();
    if (d.error) { toast('✗ ' + d.error); return; }
    // One click: a judged card is also acknowledged, so the next detection opens a new
    // card to judge instead of piling onto this one (Jonathan, 16/10).
    await _post(`/api/action/ack/${_seg(escId)}`);
    toast({ right: '✓ Marked right', wrong: '✗ Marked wrong', unsure: '? Marked unsure' }[verdict] || '✓');
    refreshObservation();
    refreshState();
  } catch (e) {
    toast('✗ ' + e.message);
  }
}

async function doAck(escId) {
  try {
    await _post(`/api/action/ack/${_seg(escId)}`);
    toast('✓ Acknowledged');
    refreshState();
  } catch (e) {
    toast('✗ ' + e.message);
  }
}

// Why the console's write buttons are greyed, or '' — read-only credentials, or (FS1c, behind
// EREGION_ACTION_QUEUE=1) the watch not taking the console's gestures now: its signed status
// missing, stale, read-only, or pinning another key than the console's. Said as the server says it.
function _writesBlocked() {
  if (_state?.read_only) return 'Read-only credentials (observe-only) — write actions disabled';
  const q = _state?.queue;
  if (q && q.on && !q.ok) return 'Action queue: ' + String(q.why || 'the watch does not take the console\'s gestures');
  return '';
}

function _guardReadOnly() {
  const why = _writesBlocked();
  if (why) {
    toast('✗ ' + why, 8000);
    return true;
  }
  return false;
}

// FS1c: a write route of the queue answers at once with its request (`pending`); its receipt is
// followed here — received, accepted, then the answer the route gave before (ok, error, refused).
const _QUEUE_SAID = { waiting: 'deposited', received: 'received by the watch', accepted: 'accepted — the watch runs it' };
async function _settled(d) {
  if (!d || !d.pending || !d.request) return d;
  let said = '';
  // The request's life and the run's (action_queue TAKE_S + RUN_S): past it, said, never a hang.
  const until = Date.now() + 750 * 1000;
  for (;;) {
    if (Date.now() > until) {
      return { ...d, pending: false, error: `request ${String(d.request).slice(0, 8)} still ${said || 'pending'}: its receipt will say it (GET /api/queue/${String(d.request)})` };
    }
    await new Promise(res => setTimeout(res, 1000));
    let f;
    try { f = await (await fetch(`/api/queue/${_seg(d.request)}`)).json(); }
    catch (e) { continue; }
    if (!f.pending) return { ...d, ...f, pending: false };
    const now = _QUEUE_SAID[f.state] || String(f.state || '');
    if (now && now !== said) { said = now; toast('⏳ Request ' + String(d.request).slice(0, 8) + ': ' + now, 4000); }
  }
}

// Preventive read-only guard: disable every button that triggers an Azure write,
// named by its action (data-on-click, #257), exactly. Ack / Cmd / Approve-rule stay active (local only).
const _WRITE_HANDLERS = [
  'doApproveAction', 'confirmRestore', 'doSnapshot',
  'confirmRelease', 'confirmUnblockIp', 'confirmReset', 'confirmExtendSubnet',
  // The modals' own buttons that run the same writes.
  'approveActionAndClose', 'approveScoped', 'snapshotAndClose',
];
function _applyReadOnlyGuards(root) {
  const why = _writesBlocked();
  if (!why) return;
  (root || document).querySelectorAll('button').forEach(b => {
    const action = b.getAttribute('data-on-click') || '';
    if (_WRITE_HANDLERS.includes(action)) {
      b.disabled = true;
      b.title = why;
    }
  });
}

async function doApproveAction(escId, vmName, opts) {
  if (_guardReadOnly()) return;
  opts = opts || {};
  // Block action: let the operator pick the blast radius first (this VM vs whole subnet).
  const esc = _escById[escId];
  if (esc && esc.action === 'block_suspicious_ip' && !opts.scope) {
    return showBlockScopeModal(escId, vmName, opts.ip || '');
  }
  toast('▶ Approving…');
  try {
    const qs = new URLSearchParams();
    if (opts.ip)    qs.set('ip', opts.ip);
    if (opts.scope) qs.set('scope', opts.scope);
    const url = `/api/action/approve/${_seg(escId)}` + (qs.toString() ? `?${qs}` : '');
    const r = await _post(url);
    const d = await _settled(await r.json());
    if (d.permission_denied) { toast('✗ Cannot execute: read-only credentials'); return; }
    // Parameterised action whose param is missing (e.g. pre-fix escalation with no IP) —
    // ask the operator for it and retry, preserving the chosen scope.
    if (d.needs_ip) {
      const entered = prompt(`IP to block for ${vmName}:`, '');
      if (entered && entered.trim()) return doApproveAction(escId, vmName, { ...opts, ip: entered.trim() });
      return;
    }
    if (d.capability_gap) { toast('✗ ' + d.error, 8000); return; }
    if (d.error) { toast('✗ ' + d.error, 6000); return; }
    const scopeNote = d.scope === 'subnet' ? ' — whole subnet' : '';
    if (d.cli_instruction) { toast('✓ Approved — run: ' + d.cli_instruction, 5000); }
    else toast('✓ Action approved and executed' + scopeNote);
    refreshState();
  } catch (e) { toast('✗ ' + e.message); }
}

// Block blast-radius choice — operator decision at click time (not stored in the
// escalation). "vm" scopes the rule to this VM's IP; "subnet" puts one any-rule on
// the subnet NSG → blocks the IP for every VM on the subnet.
function showBlockScopeModal(escId, vmName, ip) {
  document.getElementById('modal-title').textContent = `Block scope — ${vmName}`;
  document.getElementById('modal-body').innerHTML = `
    <div style="margin-bottom:12px;color:var(--text)">Where should this IP block apply?</div>
    <div style="display:flex;flex-direction:column;gap:8px">
      <button class="action" ${_on('click', 'approveScoped', escId, vmName, 'vm', ip)}
        style="text-align:left;padding:9px 11px">
        <div style="font-weight:700;color:var(--text)">🔒 This VM only <span style="color:var(--dim);font-weight:400;font-size:10px">· default</span></div>
        <div style="color:var(--dim);font-size:11px;margin-top:2px">Rule scoped to this VM's IP — other subnet VMs are untouched.</div>
      </button>
      <button class="action" ${_on('click', 'approveScoped', escId, vmName, 'subnet', ip)}
        style="text-align:left;padding:9px 11px;border-color:color-mix(in srgb,var(--orange) 45%,var(--border))">
        <div style="font-weight:700;color:var(--orange)">⚠ Whole subnet — all VMs</div>
        <div style="color:var(--dim);font-size:11px;margin-top:2px">One any-rule on the subnet NSG — blocks this IP for every VM on the subnet, incl. future ones.</div>
      </button>
    </div>`;
  document.getElementById('modal-cmd').style.display = 'none';
  document.getElementById('modal-cancel').style.display = '';
  document.getElementById('modal-confirm').style.display = 'none';
  document.getElementById('modal').classList.add('open');
}

async function setAutonomyMode(vmName, mode) {
  try {
    const r = await _post(`/api/autonomy/${_seg(vmName)}`, { mode });
    const d = await r.json();
    if (d.error) { toast('✗ ' + d.error); return; }
    toast(`✓ Mode ${mode} set for ${vmName}`);
    refreshState();
  } catch (e) { toast('✗ ' + e.message); }
}

// ── Activation (L6): no VM leaves human-only without its readiness being shown ──
const _VERDICT = {
  ready:     ['Ready', 'var(--green)', 'The autonomous response will run as designed.'],
  reserve:   ['Ready with reserves', 'var(--orange)', 'It will run, with the limitations below. Confirm you have read them.'],
  not_ready: ['Not ready', 'var(--red)', 'Glorfindel cannot act on this VM yet. Fix the points below first.'],
};

async function openActivation(vmName) {
  document.getElementById('modal-title').textContent = `Autonomous response for ${vmName}`;
  const body = document.getElementById('modal-body');
  body.innerHTML = '<div style="color:var(--dim)">Checking rights and network on Azure (nothing is changed)…</div>';
  document.getElementById('modal-cmd').style.display = 'none';
  document.getElementById('modal-cancel').style.display = '';
  const confirm = document.getElementById('modal-confirm');
  confirm.style.display = 'none';
  document.getElementById('modal').classList.add('open');
  let a;
  try { a = await (await fetch(`/api/readiness/${_seg(vmName)}`)).json(); }
  catch (e) { body.textContent = '✗ ' + e.message; refreshState(); return; }
  if (a.error) { body.textContent = '✗ ' + a.error; refreshState(); return; }
  const [label, color, lead] = _VERDICT[a.verdict] || _VERDICT.not_ready;
  const rows = (a.reasons || []).map(r => {
    const c = r.level === 'not_ready' ? 'var(--red)' : r.level === 'reserve' ? 'var(--orange)' : 'var(--dim)';
    return `<li style="margin:6px 0"><span style="color:${c};font-weight:700">${r.level === 'info' ? 'Not checked' : r.level === 'reserve' ? 'Reserve' : 'Blocking'}</span> — ${_attr(r.message)}${r.fix ? `<div style="color:var(--dim);font-size:11px">Fix: ${_attr(r.fix)}</div>` : ''}</li>`;
  }).join('');
  const ack = a.verdict === 'reserve'
    ? `<label style="display:flex;gap:6px;align-items:flex-start;margin-top:8px"><input type="checkbox" id="activation-ack"> I have read the reserves and accept them for this VM.</label>` : '';
  body.innerHTML = `<div style="font-weight:700;color:${color}">${label}</div><div style="margin:4px 0 8px">${lead}</div><ul style="margin:0;padding-left:18px">${rows}</ul>${ack}`;
  if (a.verdict === 'not_ready') { refreshState(); return; }
  confirm.style.display = '';
  confirm.textContent = 'Turn on autonomous response';
  confirm.onclick = async () => {
    if (a.verdict === 'reserve' && !document.getElementById('activation-ack')?.checked) {
      toast('Confirm the reserves first'); return;
    }
    try {
      const d = await (await _post(`/api/activate/${_seg(vmName)}`,
                                   { acknowledged: a.reserve_codes || [] })).json();
      if (d.error) { toast('✗ ' + d.error, 6000); return; }
      closeModal(); toast(`✓ Autonomous response on for ${vmName}`); refreshState();
    } catch (e) { toast('✗ ' + e.message); }
  };
  // Cancel or click outside: the selector re-renders from the real mode.
  document.getElementById('modal-cancel').onclick = () => { closeModal(); refreshState(); };
}

async function setDefaultMode(mode) {
  try {
    const r = await _post('/api/config/autonomy/default', { mode }, 'PATCH');
    const d = await r.json();
    if (d.error) { toast('✗ ' + d.error); return; }
    toast(`✓ Default mode set to ${mode}` + (d.note ? ` — ${d.note}` : ''), d.note ? 7000 : undefined);
    refreshState();
  } catch (e) { toast('✗ ' + e.message); }
}

// ── Feed ───────────────────────────────────────────────────────────────────────

// Dedup escalate feed entries with same action+vm within 5s — same underlying event
const _feedDedup = new Map(); // key → {el, count, ts}
const _FEED_DEDUP_MS = 5000;
// The gate that held a decision with no action (debug line `held_by`, agent.py).
// CPT1b: a card of incomplete telemetry (CPT1) says so in the feed, never « review ».
const _HELD_BY_WORDS = { control_plane: 'control plane (detection only)', identity: 'identity (detection only)',
  // CPT1c: a reply of the journal out of the rule's schema.
  control_plane_unreadable: 'control plane, unreadable reply (detection only)',
  control_plane_incomplete: 'control plane, incomplete telemetry (detection only)' };

// CON-D: a line that is not of today, in UTC, says its day — « yesterday », or its date (10/11,
// and its year when it is not this one); a line of today, its time alone. The day and the time
// are the server's, in UTC (api.py `_feed_when`); the page compares them to its own day.
const _FEED_DAY_MS = 86400000;
function _feedWhen(entry, now) {
  const day = String(entry.day || ''), time = String(entry.time || '');
  if (!day) return '';
  const today = new Date(now).toISOString().slice(0, 10);
  const yesterday = new Date(now - _FEED_DAY_MS).toISOString().slice(0, 10);
  if (day === today) return time + ' UTC';
  if (day === yesterday) return 'yesterday ' + time;
  const year = day.slice(0, 4) === today.slice(0, 4) ? '' : '/' + day.slice(0, 4);
  return day.slice(8, 10) + '/' + day.slice(5, 7) + year + ' ' + time;
}

// CON-D: the latest on top, each line in its place by its full moment (`at`, seconds since the
// epoch): a line that arrives late — a signal pulled from Orodruin, a file read after another —
// goes below the newer ones; of two at the same moment, the one that arrived last on top. A line
// whose moment does not read goes to the bottom. Says whether the line went on top.
function _feedPlace(list, el, entry) {
  const at = Number(entry.at);
  el._at = entry.at != null && Number.isFinite(at) ? at : -Infinity;
  el._when = { day: entry.day, time: entry.time };
  for (const row of list.children) {
    if (row._at <= el._at) { list.insertBefore(el, row); return list.firstElementChild === el; }
  }
  list.appendChild(el);
  return list.firstElementChild === el;
}

// Past midnight UTC, the lines of the page say their day again: today's become yesterday's.
let _feedDay = new Date().toISOString().slice(0, 10);
function _feedRelabel() {
  const now = Date.now(), day = new Date(now).toISOString().slice(0, 10);
  if (day === _feedDay) return;
  _feedDay = day;
  for (const row of document.getElementById('feed-list').children) {
    const ts = row.querySelector('.feed-ts');
    if (ts && row._when) ts.textContent = _feedWhen(row._when, now);
  }
}
setInterval(_feedRelabel, 60000);

function appendFeedEntry(entry) {
  const list = document.getElementById('feed-list');
  const el = document.createElement('div');
  el.className = 'feed-entry';

  const ts = _feedWhen(entry, Date.now());
  const full = entry.day ? `${String(entry.day)} ${String(entry.time)} UTC` : String(entry.timestamp || '');

  if (entry.escalate) {
    const key = `${entry.action || entry.held_by || ''}|${entry.vm || ''}`;
    const now = Date.now();
    const hit = _feedDedup.get(key);
    if (hit && (now - hit.ts) < _FEED_DEDUP_MS) {
      hit.count++;
      hit.ts = now;
      const pctEl = hit.el.querySelector('.feed-pct');
      if (pctEl) {
        const pct = entry.confidence ? Math.round(entry.confidence * 100) + '%' : '';
        pctEl.textContent = pct ? `${pct} ×${hit.count}` : `×${hit.count}`;
      }
      return; // suppress duplicate row
    }
    _feedDedup.set(key, { el, count: 1, ts: now });
    // prune stale keys
    for (const [k, v] of _feedDedup) {
      if (now - v.ts > _FEED_DEDUP_MS * 4) _feedDedup.delete(k);
    }
  }

  if (entry.type === 'signal') {
    const cls = 'ev-' + entry.event;
    const icons = {
      attack_started: '▶',
      detection: '✓',
      detection_timeout: '⚠',
      recovery_complete: '↺',
      recovery_failed: '✗',
    };
    const icon = icons[entry.event] || '·';
    el.innerHTML = `
      <span class="feed-ts" title="${_attr(full)}">${_attr(ts)}</span>
      <span class="feed-event ${_attr(cls)}">${icon} ${_attr(entry.event)}</span>
      <span class="feed-meta">${_attr(entry.ttp || '')} ${_attr(entry.vm || '')}</span>`;
  } else {
    const icon = entry.escalate ? '🚨' : entry.verified ? '✓' : entry.verified === false ? '✗' : '⚡';
    // Red for a recommendation to isolate or block; a snapshot or a hold is not an alarm.
    const disruptive = ['isolate_vm', 'block_suspicious_ip'].includes(entry.action);
    const cls  = entry.escalate ? (disruptive ? 'act-esc' : 'act-warn')
               : entry.verified ? 'act-ok' : entry.verified === false ? 'act-err' : 'act-run';
    // A detection-only decision (AL1, C2) has no action: say what held it.
    const label = entry.escalate
      ? 'escalate → ' + (entry.action || _HELD_BY_WORDS[entry.held_by] || 'review')
      : entry.action;
    const pct = entry.confidence ? Math.round(entry.confidence * 100) + '%' : '';
    el.innerHTML = `
      <span class="feed-ts" title="${_attr(full)}">${_attr(ts)}</span>
      <span class="feed-event ${cls}">${icon} ${_attr(label)}</span>
      <span class="feed-meta">${_attr(entry.ttp || '')} ${_attr(entry.vm || '')}</span>
      <span class="feed-pct">${pct}</span>`;
  }

  const onTop = _feedPlace(list, el, entry);

  // The latest is on top (CON-D): the feed stays there while the operator reads its head — moved
  // only by a line put on top, never by a late one placed further down.
  if (_autoScroll && onTop) {
    list.scrollTop = 0;
  }
}

document.getElementById('feed-list').addEventListener('scroll', function () {
  _autoScroll = this.scrollTop <= 40;
});

// ── State polling ──────────────────────────────────────────────────────────────

async function refreshState() {
  try {
    const r = await fetch('/api/state');
    const data = await r.json();
    // Resilience: only adopt a well-formed payload. A FastAPI error body ({detail:…})
    // or partial response would otherwise blank every card — keep the last good state.
    if (data && Array.isArray(data.resources)) _state = data;
    else return;
    _updatePosture();
    _autoFetchAuditOnNewVm();
    renderInfra();
    if (_watchCardsOpen()) _renderWatchCards();   // MBV1: an Ack, or a card come, said in the open window
    Console.setBreakers(_watchCards().filter(e => e.escalation_type === 'model_budget_tripped').length);   // the header, at once
    await refreshActionsData();  // parallel fetch, re-renders when ready
  } catch (e) {}
}

// Auto-fetch the readiness audit as soon as a new VM shows up (don't wait for the
// 5-min poll or a click) — the audit backend is parallel/fast now, the perceived
// delay was the UI fetch timing.
let _seenVmNames = new Set();
function _autoFetchAuditOnNewVm() {
  const names = new Set();
  (_state?.resources || []).forEach(r => r.vm_name && names.add(r.vm_name));
  (_state?.discovered_assets || []).forEach(d => d.name && names.add(d.name));
  (_state?.escalations || []).forEach(e => {
    const v = (e.resource_id || '').split('/').pop();
    if (v) names.add(v);
  });
  let hasNew = false;
  names.forEach(n => { if (!_seenVmNames.has(n)) hasNew = true; });
  _seenVmNames = names;
  if (hasNew && !_auditLoading) refreshAuditData();
}

// Posture panel — two orthogonal axes, always visible (symmetric: no "absence = active" trap).
// Colour language shared with the VM cards: blue = observe/recommend, orange = can act.
function _updatePosture() {
  const ro = !!_state?.read_only;
  const banner = document.getElementById('observe-banner');
  if (banner) banner.style.display = ro ? 'block' : 'none';
  const regime = document.getElementById('regime-badge');
  if (regime) {
    regime.textContent = ro ? '👁 OBSERVE-ONLY' : '⚡ ACTIVE';
    regime.style.color = ro ? 'var(--blue)' : 'var(--orange)';
    regime.title = ro
      ? 'Read-only credentials — Glorfindel observes and recommends, executes nothing'
      : 'Read-write credentials — Glorfindel can execute actions on Azure';
  }
  const def = _state?.autonomy_default === 'non_disruptive' ? 'non_disruptive' : 'human_only';
  const ad = document.getElementById('autonomy-default');
  if (ad) {
    const act = def === 'non_disruptive';
    // Header-only icon: ⚡ = can act, 👁 = observe — same vocabulary as the regime badge.
    ad.innerHTML = `<span style="color:var(--dim)">autonomy</span> `
      + `<span style="color:${act ? 'var(--orange)' : 'var(--blue)'};font-weight:600">`
      + `${act ? '⚡' : '👁'} ${act ? 'non-disruptive' : 'human-only'}</span>`
      + ` <span style="color:var(--dim);font-size:9px">ⓘ</span>`;
    ad.style.cursor = 'pointer';
    ad.title = 'Click — what Glorfindel can do on its own in this mode';
    ad.onclick = (e) => showCapabilityPopover(e, def);
  }
}

// ── Autonomy capability popover ──────────────────────────────────────────────────
// Surfaces what a given mode lets Glorfindel do alone (autonomous / always-gated /
// confidence gate), built from /api/state `capability`. Mode is resolved per badge.

function _capActionLabel(a) {
  return ACTION_LABELS_VERB[a]
    || a.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase());
}

function _capabilityHtml(mode) {
  const cap = _state?.capability;
  if (!cap || !cap.autonomous_actions) {
    return `<div class="cap-line">Capability data unavailable.</div>`;
  }
  const allow = new Set(cap.allow_destructive || []);
  const auto  = [...(cap.autonomous_actions || []), ...(cap.allow_destructive || [])];
  const gated = (cap.gated_actions || []).filter(a => !allow.has(a));
  const pct   = Math.round((cap.confidence_threshold ?? 0.7) * 100);
  const ro    = !!_state?.read_only;

  if (mode === 'human_only') {
    return `
      <div class="cap-title" style="color:var(--blue)">👁 HUMAN-ONLY — recommends only</div>
      <div class="cap-line">Executes nothing on its own — every action is escalated for your approval, including reversible ones.</div>
      <div class="cap-group">
        <div class="cap-head" style="color:var(--blue)">Would recommend, then wait</div>
        ${auto.map(a => `<div class="cap-item">👁 ${_attr(_capActionLabel(a))}</div>`).join('')}
      </div>`;
  }
  return `
    <div class="cap-title" style="color:var(--orange)">⚡ NON-DISRUPTIVE — acts alone</div>
    <div class="cap-group">
      <div class="cap-head" style="color:var(--green)">Runs autonomously · reversible</div>
      ${auto.map(a => `<div class="cap-item">✅ ${_attr(_capActionLabel(a))}</div>`).join('')}
    </div>
    <div class="cap-group">
      <div class="cap-head" style="color:var(--orange)">Always asks first · irreversible</div>
      ${gated.map(a => `<div class="cap-item">🔒 ${_attr(_capActionLabel(a))}</div>`).join('')}
    </div>
    <div class="cap-line" style="color:var(--orange);margin-top:8px">⚠ Any action below ${pct}% confidence is escalated anyway.</div>
    ${ro ? `<div class="cap-line" style="color:var(--blue)">👁 Observe-only credentials: autonomous actions are recommended but won't actually execute.</div>` : ''}`;
}

function showCapabilityPopover(evt, mode) {
  evt.stopPropagation();
  const pop = document.getElementById('cap-popover');
  if (!pop) return;
  pop.innerHTML = _capabilityHtml(mode);
  pop.style.display = 'block';
  const pad = 8;
  const r = pop.getBoundingClientRect();
  let x = evt.clientX;
  let y = evt.clientY + 14;
  if (x + r.width + pad > window.innerWidth)  x = window.innerWidth - r.width - pad;
  if (y + r.height + pad > window.innerHeight) y = evt.clientY - r.height - 14;
  pop.style.left = Math.max(pad, x) + 'px';
  pop.style.top  = Math.max(pad, y) + 'px';
}

function hideCapabilityPopover() {
  const pop = document.getElementById('cap-popover');
  if (pop) pop.style.display = 'none';
}

document.addEventListener('click', (e) => {
  const pop = document.getElementById('cap-popover');
  if (pop && pop.style.display === 'block' && !pop.contains(e.target)) hideCapabilityPopover();
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideCapabilityPopover(); });

setInterval(refreshState, 5000);

// ── WebSocket ──────────────────────────────────────────────────────────────────

let _ws = null;
let _wsRetry = 1000;

function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  _ws = new WebSocket(`${proto}://${location.host}/api/feed`);

  _ws.onopen = () => {
    _wsRetry = 1000;
    document.getElementById('live-dot').classList.remove('disconnected');
    document.getElementById('live-label').textContent = 'live';
    document.getElementById('feed-list').innerHTML = '';
  };

  _ws.onmessage = (evt) => {
    try {
      const entry = JSON.parse(evt.data);
      appendFeedEntry(entry);
      if (entry.type === 'action' || entry.escalate) {
        refreshState();
      }
    } catch (e) {}
  };

  _ws.onclose = () => {
    document.getElementById('live-dot').classList.add('disconnected');
    document.getElementById('live-label').textContent = 'reconnecting…';
    setTimeout(connectWS, _wsRetry);
    _wsRetry = Math.min(_wsRetry * 2, 10000);
  };

  _ws.onerror = () => _ws.close();
}

// ── Config panel ───────────────────────────────────────────────────────────────

let _configMode = false;

function toggleConfig() {
  _configMode = !_configMode;
  document.getElementById('incidents-list').style.display = _configMode ? 'none' : '';
  const cfgPanel = document.getElementById('config-panel');
  cfgPanel.style.display = _configMode ? 'flex' : 'none';
  document.getElementById('right-col-label').textContent = _configMode ? 'CONFIGURATION' : 'INFRASTRUCTURE';
  if (_configMode) refreshConfig();
  if (_configMode) _mobileTab = 'infra';   // a phone opens the configuration in the infra's tab (MOB4)
  _showMobileTab();
}

// ── On a phone (MOB4, #972, Jonathan 20/11 on a mockup, option A) ──────────────────
// Under 760 px, one section at a time — To judge, Infra, Feed —, the one body[data-m] names (the CSS
// shows it). By default To judge when cards wait, else the infra, until the operator picks a tab:
// then theirs. The configuration opens in the infra's tab, and the other tabs still answer while it
// is open (review of MOB4: they did not). Above 760 px the attribute changes nothing.
const _MOBILE_TABS = ['judge', 'infra', 'feed'];
let _mobileTab = null;                     // the tab the operator picked; null: the default
function mobileTab(which) {
  if (!_MOBILE_TABS.includes(which)) return;
  _mobileTab = which;
  _showMobileTab();
}
function _showMobileTab() {
  const tab = _mobileTab || (_toJudge.length ? 'judge' : 'infra');
  document.body.dataset.m = tab;
  for (const t of _MOBILE_TABS) {
    const b = document.getElementById('m-tab-' + t);
    if (b) b.ariaSelected = String(t === tab);
  }
  const badge = document.getElementById('m-judge-badge');
  if (badge) { badge.textContent = _toJudge.length ? String(Number(_toJudge.length)) : ''; badge.hidden = !_toJudge.length; }
}

// The server sends identifiers masked already (SEC1): its first 8 and last 4 characters.
function mask(s) {
  return s || '—';
}

function ttpStatus(c) {
  if (c.detected && c.timeout) return ['⚠ partial', 'warn'];
  if (c.detected)  return ['✓ detected', 'ok'];
  if (c.timeout)   return ['✗ timeout', 'err'];
  return ['— unknown', 'dim'];
}

// VP1c (#920): a time without a zone is never dated by a guess — a browser would take it for its own
// local time. Said unreadable, as a time that cannot be read.
const _ZONED = /(?:Z|[+-]\d{2}:?\d{2})$/i;
function _relTime(iso) {
  if (!iso) return '—';
  const t = new Date(iso).getTime();
  if (!_ZONED.test(String(iso).trim()) || Number.isNaN(t)) return 'time unreadable';
  const age = Math.floor((Date.now() - t) / 1000);
  if (age < 60) return `${age}s ago`;
  if (age < 3600) return `${Math.floor(age / 60)}m ago`;
  return `${Math.floor(age / 3600)}h ago`;
}

// COR2 (#427): how far the origins of the root shells set aside are proven — confirmed outside
// the VM (Bastion, flows), or read in the VM only (COR1, a noise reducer).
function _originProofTxt(r) {
  const n = Number(r.origin_count) || 0;
  const ok = Number(r.origin_confirmed) || 0;
  if (ok <= 0) return 'origin read in the VM only';
  if (ok >= n) return 'every one confirmed outside the VM, COR2';
  return `${ok} confirmed outside the VM (COR2), ${n - ok} read in the VM only`;
}
// SLF1 (#929): the writes of the watch's own return channel a rule set aside — how many, why —, and
// its identity not read (nothing set aside), said.
function _ownChannelTxt(r) {
  const n = Number(r.own_channel_count) || 0;
  const rows = Number(r.own_channel_rows) || 0;
  const said = n > 0
    ? `${n} write(s) of the watch's own return channel set aside (${rows} row(s) left without a card) — its identity, the container of EREGION_WATCH_CHANNEL, the objects it writes there (SLF1)${r.own_channel_last ? ' · last ' + _relTime(r.own_channel_last) : ''}`
    : '';
  const unread = r.own_channel_unread
    ? `return channel configured, the watch's identity not read (${_relTime(r.own_channel_unread)}): none of its writes set aside`
    : '';
  // SLF1b (#976): rows whose BlobWriters column could not be read — nothing set aside of them.
  const bad = Number(r.own_channel_unparsed) || 0;
  const unparsed = bad > 0
    ? `${bad} row(s) whose BlobWriters column could not be read: nothing set aside of them (SLF1b)${r.own_channel_unparsed_last ? ' · last ' + _relTime(r.own_channel_unparsed_last) : ''}`
    : '';
  return [said, unread, unparsed].filter(Boolean).join(' · ');
}

// SLF2 (#1010): Orodruin's writes in its exercise channel a rule set aside — how many, why —, and why
// nothing can be (its identity unset or no object id, the channel unset), said.
function _exerciseChannelTxt(r) {
  const n = Number(r.exercise_channel_count) || 0;
  const rows = Number(r.exercise_channel_rows) || 0;
  const said = n > 0
    ? `${n} write(s) of Orodruin in its exercise channel set aside (${rows} row(s) left without a card) — its identity (EREGION_ORODRUIN_PRINCIPAL_ID), the container of EREGION_EXERCISE_CHANNEL, its account (SLF2)${r.exercise_channel_last ? ' · last ' + _relTime(r.exercise_channel_last) : ''}`
    : '';
  const config = {
    'unset': 'exercise channel configured, EREGION_ORODRUIN_PRINCIPAL_ID unset: none of its writes set aside, every row a card (SLF2)',
    'malformed': 'EREGION_ORODRUIN_PRINCIPAL_ID is no object id: none of its writes set aside, every row a card (SLF2)',
    'no channel': 'EREGION_EXERCISE_CHANNEL unset or refused (its URL not one container of a storage account): none of Orodruin\'s writes set aside (SLF2)',
  }[r.exercise_channel_config] || '';
  return [said, config].filter(Boolean).join(' · ');
}

// MID1 (#981): the rows of entra-credential-added set aside as the certificate Azure puts on a managed
// identity it creates — how many, why —, and the id of the tenant's principal unset or no object id
// (nothing set aside), said.
function _msiCertificateTxt(r) {
  const n = Number(r.msi_certificate_count) || 0;
  const said = n > 0
    ? `${n} row(s) set aside, no card: the certificate Azure puts on a managed identity it creates — by the tenant's « Managed Service Identity » principal (EREGION_ENTRA_MSI_ACTOR_ID), « Add service principal » on a ServicePrincipal, every credential an AsymmetricX509Cert of usage Verify (MID1)${r.msi_certificate_last ? ' · last ' + _relTime(r.msi_certificate_last) : ''}`
    : '';
  const config = r.msi_certificate_config === 'malformed'
    ? 'EREGION_ENTRA_MSI_ACTOR_ID is no object id: nothing set aside, every row a card (MID1)'
    : r.msi_certificate_config === 'unset'
      ? 'EREGION_ENTRA_MSI_ACTOR_ID unset: nothing set aside, every row a card (MID1)'
      : '';
  return [said, config].filter(Boolean).join(' · ');
}

function showRuleDetail(rule) {
  const statusTxt = rule.last_error
    ? `⚠ error: ${rule.last_error}`
    : rule.last_match
      ? `✓ last match ${_relTime(rule.last_match)} · ${rule.match_count} total`
      : rule.last_poll
        ? `polled ${_relTime(rule.last_poll)} · no match yet`
        : 'not polled yet';
  // ADM1: the sudo set aside as the administrators' expected ones (no card), counted.
  const expectedTxt = rule.expected_count > 0
    ? `${rule.expected_count} expected sudo set aside, no card${rule.origin_count > 0 ? ` (${rule.origin_count} root shell(s) from an expected origin, COR1 — ${_originProofTxt(rule)})` : ''} · last ${_relTime(rule.expected_last)} — glorfindel report lists them`
    : '';
  // COR1: the correlation's queries, what they decided, what they could not read; COR2: the
  // origins confirmed outside the VM, and those left a card for want of a trace there.
  const co = rule.correlation || {};
  const corrTxt = co.queries > 0
    ? `correlation (COR1): ${co.queries} quer${co.queries > 1 ? 'ies' : 'y'} · ${co.origin || 0} root shell(s) set aside by origin · ${co.card || 0} carded by origin · ${co.unknown || 0} unknown (card)${co.confirmed ? ` · ${co.confirmed} confirmed outside the VM (COR2)` : ''}${co.unconfirmed ? ` · ${co.unconfirmed} without a trace outside the VM (card)` : ''}${co.compromised ? ` · ${co.compromised} login(s) after brute force (critical)` : ''}${co.unchecked ? ` · ${co.unchecked} not checked` : ''}`
    : '';

  document.getElementById('modal-title').textContent =
    `${rule.name}${rule.ttp ? '  ·  ' + rule.ttp : ''}`;

  const bodyEl = document.getElementById('modal-body');
  bodyEl.innerHTML = `
    <div style="margin-bottom:8px;color:var(--text)">${_attr(rule.description || '—')}</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px">
      <span class="cfg-badge dim">${_attr(rule.source)}</span>
      <span class="cfg-badge dim">backend: ${_attr(rule.monitoring_backend_name || '—')}</span>
      <span class="cfg-badge dim">every ${_attr(rule.interval_s)}s</span>
      ${rule.last_error
        ? '<span class="cfg-badge err">error</span>'
        : rule.last_match
          ? '<span class="cfg-badge ok">matched</span>'
          : '<span class="cfg-badge dim">no match</span>'}
    </div>
    <div style="font-size:10px;color:var(--dim);margin-bottom:8px">${_attr(statusTxt)}</div>
    ${expectedTxt ? `<div style="font-size:10px;color:var(--dim);margin-bottom:8px">${_attr(expectedTxt)}</div>` : ''}
    ${corrTxt ? `<div style="font-size:10px;color:var(--dim);margin-bottom:8px">${_attr(corrTxt)}</div>` : ''}
    ${_ownChannelTxt(rule) ? `<div style="font-size:10px;color:var(--dim);margin-bottom:8px">${_attr(_ownChannelTxt(rule))}</div>` : ''}
    ${_exerciseChannelTxt(rule) ? `<div style="font-size:10px;color:var(--dim);margin-bottom:8px">${_attr(_exerciseChannelTxt(rule))}</div>` : ''}
    ${_msiCertificateTxt(rule) ? `<div style="font-size:10px;color:var(--dim);margin-bottom:8px">${_attr(_msiCertificateTxt(rule))}</div>` : ''}
    <div style="font-size:10px;color:var(--dim);margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Query</div>
    <div class="modal-query">${_attr((rule.query || '').trim())}</div>`;

  document.getElementById('modal-cmd').style.display = 'none';
  const btn = document.getElementById('modal-confirm');
  btn.textContent = 'Close';
  btn.className = 'action';
  btn.onclick = closeModal;
  document.querySelector('.modal').classList.add('wide');
  document.getElementById('modal').classList.add('open');
}

function showRuleByIdx(idx) {
  const rule = _rulesCache[idx];
  if (rule) showRuleDetail(rule);
}

async function showIsolationModal(vmName) {
  const _tryShow = () => {
    const actions = (_actionsCache[vmName]?.actions || []);
    const idx = actions.findIndex(a =>
      ['isolate_vm', 'block_suspicious_ip', 'release_isolation', 'revoke_temp_access'].includes(a.action));
    return idx;
  };

  let idx = _tryShow();
  if (idx >= 0) { showReasoning(vmName, idx); return; }

  // Cache stale or not yet populated — force-fetch then retry
  document.getElementById('modal-title').textContent = 'Decision — ' + vmName;
  document.getElementById('modal-body').textContent = 'Loading reasoning…';
  document.getElementById('modal-cmd').style.display = 'none';
  const btn = document.getElementById('modal-confirm');
  btn.textContent = 'Close';
  btn.className = 'action';
  btn.onclick = closeModal;
  document.getElementById('modal').classList.add('open');

  try {
    const r = await fetch(`/api/actions/${_seg(vmName)}?limit=15`);
    const d = await r.json();
    _actionsCache[vmName] = { actions: d.actions || [], fetchedAt: Date.now() };
  } catch (e) {}

  idx = _tryShow();
  if (idx >= 0) { closeModal(); showReasoning(vmName, idx); return; }

  // Still nothing
  document.getElementById('modal-body').textContent =
    'No reasoning available yet.\nThe remediation cycle may still be running — retry in a few seconds.';
}

// ── The plan of an identity card (IR1a) ─────────────────────────────────────────────
// Written by the watch's code from the row of Entra's log, its ids read on Graph (read only):
// the verbs in their order, then the steps for a human, each with its complete command, what
// was not read (never invented), its side effect and its way back. « Verify » asks the watch to
// read Graph again: held, not held or unreadable, noted on the card's thread. Every field is
// text from the outside (an application's name chosen by an attacker): _attr, always.
const _CHECK_WORDS  = { held: 'held', not_held: 'NOT held', unreadable: 'unreadable (never « held »)' };
const _CHECK_COLORS = { held: 'var(--green)', not_held: 'var(--red)', unreadable: 'var(--yellow)' };
function _planLine(label, value, code) {
  if (!value) return '';
  const v = code ? `<code style="color:var(--blue)">${_attr(value)}</code>` : _attr(value);
  return `<div style="font-size:10px;padding-left:10px"><span style="color:var(--dim)">${_attr(label)}</span> ${v}</div>`;
}
function _planItem(i) {
  const verb = i.verb ? `<code style="color:var(--cyan)">${_attr(i.verb)}</code> ` : '';
  const unread = (i.params || []).filter(p => !p.read)
    .map(p => `<div style="font-size:10px;padding-left:10px;color:var(--yellow)">not read: ${_attr(p.name)} — ${_attr(p.why || '')}</div>`).join('');
  return `<div style="padding:3px 0 3px 8px;border-left:1px solid var(--border);margin:4px 0">
      <div style="font-size:11px">${Number(i.n)}. ${verb}${_attr(i.what)}${i.optional ? ' <span style="color:var(--dim)">(if the author is not expected)</span>' : ''}</div>
      ${i.why_human ? `<div style="color:var(--dim);font-size:10px;padding-left:10px">${_attr(i.why_human)}</div>` : ''}
      ${_planLine('command', i.command, true)}${unread}
      ${_planLine('to find it', i.find, true)}${_planLine('before', i.before, true)}
      ${_planLine('side effect', i.side_effect, false)}${_planLine('way back', i.rollback, false)}
    </div>`;
}
function _planCheck(c) {
  const items = (c.items || []).map(x => `<div style="font-size:10px;padding-left:10px">
      <span style="color:${_CHECK_COLORS[x.state] || 'var(--dim)'}">${_attr(_CHECK_WORDS[x.state] || x.state)}</span>
      ${Number(x.n)}. ${_attr(x.why)}${x.optional ? ' <span style="color:var(--dim)">(not counted)</span>' : ''}</div>`).join('');
  return `<div style="margin:4px 0"><span style="color:${_CHECK_COLORS[c.verdict] || 'var(--dim)'};font-weight:700">
      ${_attr(_CHECK_WORDS[c.verdict] || c.verdict)}</span> <span style="color:var(--dim);font-size:10px">${_attr(c.at)}
      ${c.why ? ' — ' + _attr(c.why) : ''}</span>${items}</div>`;
}
function _identityPlan(e) {
  const plan = e.identity_plan;
  if (!plan || typeof plan !== 'object') return '';
  const items = plan.items || [];
  const verbs = items.filter(i => i.by === 'executor').map(_planItem).join('');
  const steps = items.filter(i => i.by !== 'executor').map(_planItem).join('');
  const graph = plan.graph || {};
  const checks = (e.identity_checks || []).slice(-3).reverse().map(_planCheck).join('');
  const asked = e.identity_check_requested
    ? `<div style="color:var(--dim);font-size:10px">Verify asked at ${_attr(e.identity_check_requested)} — the watch answers at its next pass</div>` : '';
  const canCheck = items.some(i => i.verifiable);
  // IR1f: an identity of the defense in the finding, an author never_target lists, an hour not
  // read — said ahead of the steps (the watch's French, as the plan's other words).
  const notes = (Array.isArray(plan.protected) ? plan.protected : []).concat(plan.event_at_why ? [plan.event_at_why] : []);
  // « An identity of the defense » for Glorfindel's alone; any other never_target protects, « Protected ».
  const title = plan.defense === 'glorfindel' ? 'An identity of the defense'
    : (plan.defense || (Array.isArray(plan.protected) && plan.protected.length) ? 'Protected' : 'Note');
  const said = notes.length ? `<div style="color:var(--yellow);font-size:10px;margin:4px 0">
      <span style="font-weight:700">${_attr(title)}</span>
      ${notes.map(x => `<div style="padding-left:10px">⚠ ${_attr(x)}</div>`).join('')}</div>` : '';
  return `<div style="margin-top:8px;border-top:1px solid var(--border);padding-top:6px">
      <div style="display:flex;align-items:center;gap:6px">
        <span style="font-weight:700;font-size:11px">Plan</span>
        <span style="color:var(--dim);font-size:10px">written by the code, never the model · no executor before IR1c: every item by hand, with your account</span>
        ${canCheck ? `<button class="action" style="margin-left:auto" ${_on('click', 'verifyIdentity', e.id)}>🔎 Verify</button>` : ''}
      </div>
      ${graph.read ? '' : `<div style="color:var(--yellow);font-size:10px">Graph not read: ${_attr(graph.why || '')} — each parameter not read is marked, never invented</div>`}
      <div style="color:var(--text);font-size:10px;margin:4px 0">${_attr(plan.confirm || '')}</div>
      ${said}
      ${verbs ? `<div style="color:var(--dim);font-size:10px;margin-top:4px">Verbs (the identity executor's, IR1c)</div>${verbs}` : ''}
      ${steps ? `<div style="color:var(--dim);font-size:10px;margin-top:4px">Steps for a human</div>${steps}` : ''}
      ${plan.note ? `<div style="color:var(--dim);font-size:10px">${_attr(plan.note)}</div>` : ''}
      ${asked}${checks}
    </div>`;
}
// « Verify »: the request written on the card; the watch reads Graph and notes the result. The
// page waits a minute for it, then says it did not come (a watch stopped answers nothing).
async function verifyIdentity(escId) {
  const before = ((_escById[escId] || {}).identity_checks || []).length;
  let d;
  try {
    d = await (await _post(`/api/identity/verify/${_seg(escId)}`)).json();
  } catch (err) { toast('✗ ' + err.message); return; }
  if (d.error) { toast('✗ ' + d.error); return; }
  toast('🔎 Asked to the watch — it reads Graph and notes the result on the card');
  for (let n = 0; n < 12; n++) {
    await new Promise(r => setTimeout(r, 5000));
    await refreshState();
    const e = _escById[escId];
    const checks = (e && e.identity_checks) || [];
    if (checks.length > before) {
      const last = checks[checks.length - 1];
      toast('Verify: ' + (_CHECK_WORDS[last.verdict] || last.verdict), 6000);
      const vm = _ownTile(e) || (e.resource_id || '').split('/').pop();
      if (document.getElementById('modal').classList.contains('open') && vm) showEscModal(vm);
      return;
    }
  }
  toast('Verify: no answer from the watch in a minute — is it running? The request stays on the card.', 8000);
}

// JUG1 (#760): one card's details — its own, never its group's first: what it is about, its
// reason, the model's explanation, what an action taken alone did and how it was checked, and the
// way to its verdict (TO JUDGE: the one place a card is judged). `own`: a card among several, its
// head said (title, when, id), its steps with it.
function _isDecisionCard(e) {
  return !(e.action === 'improve_detection' && e.proposal_id) && !_NOT_DECISIONS.has(e.escalation_type)
    && !String(e.signal_id || '').startsWith('reassert-');
}
function _judgeWay(e) {
  if (!_isDecisionCard(e)) return '';
  return e.verdict
    ? `<span style="font-size:9px;color:var(--dim)">judged: ${_attr(e.verdict)}</span>`
    : `<a class="judge-link" ${_on('click', 'openJudgeCard', e.id)} title="Its details, and its verdict">to judge ▸</a>`;
}
function _executedDetail(e) {
  const x = e && e.executed;
  if (!_isExecuted(e) || !x || typeof x !== 'object') return '';
  const v = (x.verification && typeof x.verification === 'object') ? x.verification : {};
  const check = [v.verified === true ? 'verified' : '', v.method || '',
    v.nics_covered ? `${Number(v.nics_covered)} NIC(s)` : '', v.nsg || '', v.drain ? 'cut ' + v.drain : '',
    v.verified_at ? String(v.verified_at).slice(0, 19).replace('T', ' ') + ' UTC' : '']
    .filter(Boolean).map(w => _attr(w)).join(' · ');
  const evidence = (Array.isArray(x.evidence) ? x.evidence : []).slice(0, 8)
    .map(w => `<div style="color:var(--dim);font-size:10px;padding:1px 0 1px 8px">• ${_attr(w)}</div>`).join('');
  return `<div class="esc-context" style="color:var(--green)" title="It ran alone, and Azure read it back: undo it, if judged wrong, by the usual paths">✓ done alone · mode ${_attr(x.mode || '?')}${check ? ` · ${check}` : ''}</div>
    ${x.note ? `<div class="esc-context" style="color:var(--yellow)">⚠ ${_attr(x.note)}</div>` : ''}
    ${evidence ? `<div style="color:var(--dim);font-size:10px;margin-top:4px">evidence (the detection's row):</div>${evidence}` : ''}`;
}
function _cardDetail(e, vmName, own) {
  const head = own
    ? `<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:8px;padding-top:6px;border-top:1px dashed var(--border);font-size:10px">
        <span style="color:var(--text);font-weight:700">${_attr(escTitle(e))}</span>
        <span style="color:var(--dim)">${_attr(e.first_seen ? _relTime(e.first_seen) : '')} · ${_attr(String(e.id || '').slice(0, 8))}</span>
        <span style="margin-left:auto">${_judgeWay(e)}</span>
      </div>
      <div style="color:var(--dim);font-size:10px">${_escCtx(e, e.confidence ? Math.round(e.confidence * 100) + '%' : '', false)}</div>`
    : (_judgeWay(e) ? `<div style="margin-bottom:4px">${_judgeWay(e)}</div>` : '');
  // A card among several keeps its own plan (an identity card's, with its Verify: IR1a) or its steps,
  // and its proposed query (JUG1 review).
  const rest = own ? `${e.identity_plan ? _identityPlan(e) : _cardSteps(e)}${_cardQuery(e)}` : '';
  return `${head}${_cardBody(e, vmName)}${rest}`;
}
function _cardQuery(e) {
  return e.proposed_query
    ? `<pre style="background:var(--bg2);border-left:2px solid var(--cyan);padding:8px;font-size:10px;
         color:var(--blue);white-space:pre-wrap;overflow-x:auto;margin:6px 0;border-radius:0 4px 4px 0">${_attr(e.proposed_query.trim())}</pre>`
    : '';
}
// What a card says, the same wherever it is opened (a tile's details, TO JUDGE): what it is about,
// its reason, the model's explanation, what an action taken alone did.
function _cardBody(e, vmName) {
  const explanation = e.explanation && e.explanation !== e.reason
    ? `<div style="color:var(--dim);font-size:10px;line-height:1.5;margin-top:3px">${_attr(e.explanation)}</div>` : '';
  return `${_targetNote(e, vmName)}${_ceilingNote(e)}
    <div style="color:var(--text);font-size:11px;line-height:1.6">${_attr(e.reason || '')}</div>
    ${explanation}${_executedDetail(e)}`;
}
// RDW1 (#994): the rule's ceiling brought the model's decision back — both said, the one the card holds
// (or that ran alone) and the model's own, with its confidence and the rule's reason. The isolation stays
// a human's gesture, from the card (cliCommand). Nothing raw: every field through _attr.
function _ceilingOf(e) {
  const c = e && e.ceiling;
  return c && typeof c === 'object' && c.proposed ? c : null;
}
function _ceilingNote(e) {
  const c = _ceilingOf(e);
  if (!c) return '';
  const pct = Number(c.confidence) > 0 ? ` (${Math.round(Number(c.confidence) * 100)}%)` : '';
  return `<div class="esc-context" style="color:var(--yellow)" title="The rule caps what its detection may lead to, whatever the model's confidence: the model's proposal is kept here, never run alone">⛔ rule ceiling${c.rule ? ` · ${_attr(c.rule)}` : ''} — model proposed: ${_attr(actionLabelVerb(c.proposed))}${pct} · brought back to: ${_attr(actionLabelVerb(c.lowered || 'snapshot'))}${c.why ? ` · ${_attr(c.why)}` : ''}</div>`;
}
// The gesture the ceiling leaves to a human (RDW1), on a card that holds another action (the snapshot):
// the model's isolation, a comment only — the block is run as a whole, and its snapshot must never isolate
// too. The ceiling's own card proposes it (approvable in one click). Never on a card that names no VM
// (cliCommand returns before, ATT1).
function _ceilingCommand(e) {
  const c = _ceilingOf(e);
  if (!c || c.proposed !== 'isolate_vm' || e.action === 'isolate_vm') return '';
  return `# rule ceiling: the model proposed to isolate — its own card proposes it; only after judging: glorfindel isolate ${_vmArg(e.resource_id)} --yes\n`;
}
function _cardSteps(e) {
  return _looseSteps(e) + (e.suggested_steps || [])
    .map(st => `<div style="color:var(--dim);font-size:10px;padding:2px 0 2px 8px">• ${_attr(st)}</div>`).join('');
}
// ATT1 (#936): the model's steps of an unattributed card may name the VM it is filed on, which the
// detection does not name — said before them, by the page, never by the model.
function _looseSteps(e) {
  const loose = _unattributed(e);
  if (!loose || !(e.suggested_steps || []).length) return '';
  return `<div style="color:var(--yellow);font-size:10px;padding:2px 0 2px 8px">⚓ ${_attr(_unattributedTxt(loose))}; judge from the CLI — these steps aim at the VM the card is filed on</div>`;
}

// JUG1: a line of TO JUDGE opens its card — its details as the store holds them (a card still
// pending, with all it says; an acknowledged one, as TO JUDGE carries it), and its verdict there.
function openJudgeCard(escId) {
  const listed = _toJudge.find(c => c.id === escId);
  const e = Object.assign({}, listed || {}, _escById[escId] || {});
  if (!e.id) { toast(`Not in TO JUDGE (older than 7 days?) — glorfindel verdict ${escId} right|wrong|unsure`); return; }
  const vmName = _ownTile(e) || String(e.resource_id || '').split('/').pop();
  const label = _isExecuted(e) ? `${actionLabel(e.action)} — done alone, to judge`
    : (e.action ? actionLabelVerb(e.action) : escTitle(e));
  // SLF1: a detection attributed to no VM is about none — never its anchor's name in the title.
  document.getElementById('modal-title').textContent = `To judge — ${label} — ${_unattributed(e) ? 'not attributed' : (_tileSaid(e) || vmName)}`;
  document.getElementById('modal-cmd').style.display = 'none';
  document.getElementById('modal-cancel').style.display = 'none';
  const bodyEl = document.getElementById('modal-body');
  const verdicts = e.verdict || !listed
    ? `<span style="font-size:10px;color:var(--dim)">${e.verdict ? 'judged: ' + _attr(e.verdict) : 'not in TO JUDGE'}</span>`
    : `<input id="judge-modal-note" placeholder="note (optional): why" maxlength="300">
       <button class="action" title="The recommendation was right" ${_on('click', 'judgeFromModal', e.id, 'right')}>✓ Right</button>
       <button class="action" style="color:var(--red)" title="False positive, or a disproportionate action" ${_on('click', 'judgeFromModal', e.id, 'wrong')}>✗ Wrong</button>
       <button class="action" style="color:var(--dim)" title="Can't tell with what is known" ${_on('click', 'judgeFromModal', e.id, 'unsure')}>? Unsure</button>`;
  bodyEl.innerHTML = `<div style="border-left:2px solid var(--purple);padding:10px;background:color-mix(in srgb,var(--purple) 4%,var(--bg1))">
      <div style="color:var(--dim);font-size:10px;margin-bottom:6px">${_escCtx(e, e.confidence ? Math.round(e.confidence * 100) + '%' : '', false)}${e.rule_name ? ` · rule ${_attr(e.rule_name)}` : ''} · ${_attr(e.first_seen ? _relTime(e.first_seen) : '')} · ${_attr(e.status || '')}</div>
      ${_cardBody(e, vmName)}${_cardSteps(e)}
      ${e.verdict || !listed ? '' : _proposedLine(listed, true)}
      <div class="judge-actions" style="margin-top:8px">${verdicts}</div>
    </div>`;
  const btn = document.getElementById('modal-confirm');
  btn.textContent = 'Close';
  btn.className = 'action';
  btn.onclick = () => {
    closeModal();
    document.getElementById('modal-cancel').style.display = '';
  };
  document.querySelector('.modal').classList.add('wide');
  document.getElementById('modal').classList.add('open');
}

function showEscModal(vmName) {
  // A tile's cards, as the tile shows them (AL1c: the identities' tile, an NSG's card on a VM it
  // covers); a card's own resource otherwise.
  const tile = _tiles.get(vmName);
  const escs = Object.values(_escById).filter(e => tile ? _onTile(e, tile) :
    (e.resource_id.split('/').pop() === vmName || e.resource_id === vmName));
  if (!escs.length) { toast('No active escalations for ' + vmName); return; }

  const groups = _groupEscs(escs);
  document.getElementById('modal-title').textContent =
    `Escalations — ${(tile && tile.label) || vmName} (${groups.length}${groups.length < escs.length ? `, ${escs.length} total` : ''})`;
  document.getElementById('modal-cmd').style.display = 'none';
  document.getElementById('modal-cancel').style.display = 'none';

  const bodyEl = document.getElementById('modal-body');
  bodyEl.innerHTML = groups.map(group => {
    const e     = group[0];
    const ids   = group.map(g => g.id).join(','); // CSV — one string argument of the button's action (_on)
    const count = Number(group.length);
    const isModeHold        = _isHeld(e);
    const isSnapshotPending = _isSnapshotPending(e);
    const isWriteBlocked    = e.escalation_type === 'write_blocked';
    const isActionFailed    = e.escalation_type === 'action_failed';
    const isRule            = e.action === 'improve_detection' && e.proposal_id;
    const pct2  = e.confidence ? Math.round(e.confidence * 100) + '%' : '';
    const label = isModeHold
      ? `${actionLabelVerb(e.action)}${pct2 ? ` (${pct2})` : ''} — ${_heldWord(e)}`
      : _isExecuted(e)    ? `${actionLabel(e.action)} — done alone, to judge`
      : isSnapshotPending ? 'Snapshot recommended'
      : isWriteBlocked    ? `${actionLabelVerb(e.action) || e.action || '?'} — write blocked`
      : isActionFailed    ? `${actionLabelVerb(e.action) || e.action || '?'} — failed`
      : _sharedTitle(group);   // RTT1b: as its tile titles it
    // type already encoded in title for these — keep ctx lean
    const ctx   = _escCtx(e, '', isModeHold || isWriteBlocked || isActionFailed, _sharedRuleTitle(group), _groupRules(group).size > 1);
    // An identity card with its plan (IR1a) shows the plan — the same steps, structured, with Verify.
    const steps = e.identity_plan ? _identityPlan(e) : _looseSteps(e) + (e.suggested_steps || [])
      .map(s => `<div style="color:var(--dim);font-size:10px;padding:2px 0 2px 8px">• ${_attr(s)}</div>`).join('');
    const query = _cardQuery(e);
    const pid   = e.proposal_id || '';
    const countBadge = count > 1
      ? `<span style="font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;
                      background:color-mix(in srgb,var(--purple) 15%,transparent);
                      color:var(--purple)">×${count}</span>` : '';
    const modalBtns = isRule
      ? `<button class="action" style="color:var(--green)" ${_on('click', 'approveRuleAndClose', pid, e.id)}>✓ Approve</button>
         <button class="action" style="color:var(--red)"   ${_on('click', 'rejectRuleAndClose', pid, e.id)}>✗ Reject</button>`
      : e.escalation_type === 'readiness_hold'
      ? `<button class="action primary" ${_on('click', 'openActivation', vmName)}>⚡ Review & turn on</button>
         <button class="action" ${_on('click', 'ackAllAndClose', ids)}>✓ Ack</button>
         <button class="action" ${_on('click', 'openCommandModal', e.id)}>📋 Cmd</button>`
      : isModeHold
      ? `<button class="action primary" ${_on('click', 'approveActionAndClose', e.id, vmName)}>▶ Approve & execute</button>
         <button class="action" ${_on('click', 'ackAllAndClose', ids)}>✓ Ack</button>
         <button class="action" ${_on('click', 'openCommandModal', e.id)}>📋 Cmd</button>`
      : isSnapshotPending
      ? `<button class="action" ${_on('click', 'snapshotAndClose', vmName)}>📸 Snapshot</button>
         <button class="action" ${_on('click', 'ackAllAndClose', ids)}>✓ Ack</button>
         <button class="action" ${_on('click', 'openCommandModal', e.id)}>📋 Cmd</button>`
      : `<button class="action" ${_on('click', 'ackAllAndClose', ids)}>✓ Ack</button>
         <button class="action" ${_on('click', 'openCommandModal', e.id)}>📋 Cmd</button>`;
    // JUG1: a group of several cards shows each of them, every one readable and judged on its own
    // — the tile of an NSG folded six into one, and its details showed the first only (bench, 12/11).
    const body = count > 1
      ? `<div style="color:var(--dim);font-size:10px">${count} cards, each with its own details:</div>
         ${group.map(g => _cardDetail(g, vmName, true)).join('')}`
      : `${ctx ? `<div style="color:var(--dim);font-size:10px;margin-bottom:6px">${ctx}</div>` : ''}
         ${_cardDetail(e, vmName, false)}${query}${steps}`;
    return `<div style="border-left:2px solid var(--purple);padding:10px;margin-bottom:10px;background:color-mix(in srgb,var(--purple) 4%,var(--bg1))">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;flex-wrap:wrap">
        <span style="color:var(--purple);font-weight:700;font-size:12px">${_attr(label)}</span>
        ${countBadge}
        <span style="margin-left:auto;display:flex;gap:6px">${modalBtns}</span>
      </div>
      ${body}
    </div>`;
  }).join('');

  const btn = document.getElementById('modal-confirm');
  btn.textContent = 'Close';
  btn.className = 'action';
  btn.onclick = () => {
    closeModal();
    document.getElementById('modal-cancel').style.display = '';
  };
  document.querySelector('.modal').classList.add('wide');
  document.getElementById('modal').classList.add('open');
  _applyReadOnlyGuards(bodyEl);
}

// The console's sections (/api/sections): Glorfindel always, each injector active or greyed.
function _sectionsConfig() {
  const d = _sectionsSeen;
  if (!d) return '';
  const rows = (d.sections || []).map(x => `<div class="cfg-row">
      <span class="cfg-key">${_attr(x.label)}</span>
      <span class="cfg-val">${x.always ? 'always on — the product'
        : x.active ? `<span class="cfg-badge ok">active</span> <span style="color:var(--dim)">${_attr(x.why)}</span>`
        : `<span class="cfg-badge">not set up</span> <span style="color:var(--dim)">${_attr(x.why)}</span>`}</span>
    </div>`).join('');
  return `<div class="cfg-section">
      <div class="cfg-section-title">Sections</div>${rows}
      <div style="color:var(--dim);font-size:10px;padding:4px 0 0">
        ${d.override ? 'Chosen at start (<code>--sections</code>).' : 'Detected from this host\'s runs.'}
        Annatar and Gothmog require Glorfindel; to choose them: <code>eregion console --sections annatar,gothmog</code>
        (or <code>EREGION_CONSOLE_SECTIONS</code>).
      </div>
    </div>`;
}
let _sectionsSeen = null;
Console.onSections(d => { _sectionsSeen = d; if (_configMode) refreshConfig(); });

// CFG3 (#1139): the view « Relaxed » (/api/config/relaxed) — what glorfindel-config.yaml relaxes, computed by
// the watch in its own directory (runs/glorfindel/config/relaxed.json); read here, never computed nor written.
// A view absent, unreadable, old, or a file refused: said, never shown as « nothing relaxed ».
let _relaxedSeen = null;
const _RELAXED_KIND = {
  default_mode: 'default mode', mode: 'mode', exclusion: 'exclusion', never_block: 'never_block',
  expected_admins: 'expected admins', forensic_access: 'investigation access', exposed_zone: 'exposed zone',
  named_network: 'named network', discovery_off: 'discovery off', expected_origin: 'expected origin',
};
const _LATENT_TIP = 'Changes nothing today: it screens the VM from the pattern and the default, or another entry '
  + 'gives the same — the day those go back to human-only or away, this one still relaxes.';
// CFG3c (#1154): an expected origin is in force only while the watch reads GLORFINDEL_LATERAL on — the state the
// watch wrote in the line (`in_force`), never guessed here: an expected origin without `in_force: true` is
// shown without effect, never as active.
const _OFF_TIP = 'Written, without effect: the watch reads GLORFINDEL_LATERAL off — nothing is set aside until it is on.';
const _ON_TIP = 'In force: the watch reads GLORFINDEL_LATERAL on — a detection from it is set aside, said and counted.';

function _forceBadge(e) {
  if (e.kind !== 'expected_origin' && e.in_force !== false) return '';
  return e.in_force === true
    ? ` <span class="cfg-badge warn" title="${_attr(_ON_TIP)}">in force</span>`
    : ` <span class="cfg-badge dim" title="${_attr(_OFF_TIP)}">without effect</span>`;
}

function _relaxedRow(e) {
  const reason = e.reason ? `« ${_attr(e.reason)} »` : '<span style="color:var(--dim)">no reason</span>';
  return `<div class="cfg-row relaxed-row" title="${_attr((Array.isArray(e.why) ? e.why : []).join(' ; '))}">
      <span class="cfg-key">${_attr(e.object)}</span>
      <span class="cfg-val">${_attr(_RELAXED_KIND[e.kind] || e.kind)} · ${_attr(e.what)}${e.latent
        ? ` <span class="cfg-badge warn" title="${_attr(_LATENT_TIP)}">latent</span>` : ''}${_forceBadge(e)} · ${reason}
        <span style="color:var(--dim)">· ${_attr((e.designates || {}).said || '')} · by ${_attr(e.by)}${e.since
          ? ' · since ' + _attr(e.since) : ''} · ${_attr(e.where)}</span></span>
    </div>`;
}

function _relaxedConfig() {
  const d = _relaxedSeen;
  if (!d) return '';
  const view = d.view || {};
  const entries = Array.isArray(view.entries) ? view.entries : null;
  const disc = view.discovery || {};
  const warns = [d.said, (view.override || {}).said || '', (view.lateral || {}).said || '',
    d.file_changed ? 'glorfindel-config.yaml changed since the watch computed this view: it computes it again within a minute' : '',
    entries && disc.state && disc.state !== 'read' ? `discovery not read (${disc.error || 'unknown'}): what a pattern designates is not known` : '',
  ].filter(Boolean).map(w => `<div class="relaxed-warn">⚠ ${_attr(w)}</div>`).join('');
  const none = entries && !entries.length
    ? '<div style="color:var(--dim);font-size:11px">Nothing relaxed in glorfindel-config.yaml.</div>' : '';
  return `<div class="cfg-section">
      <div class="cfg-section-title">Relaxed${entries ? ' · ' + Number(entries.length) : ''}</div>
      ${warns}${(entries || []).map(_relaxedRow).join('')}${none}
      <div style="color:var(--dim);font-size:10px;padding:4px 0 0">
        Read-only: computed by the watch from glorfindel-config.yaml (runs/glorfindel/config/relaxed.json), each
        entry classed as the watch classes a change. Who and when: unknown until the history of the configuration.
      </div>
    </div>`;
}

async function _fetchRelaxed() {
  try {
    const r = await fetch('/api/config/relaxed');
    _relaxedSeen = r.ok ? await r.json() : { said: `the view could not be read (HTTP ${Number(r.status)})`, view: null };
  } catch (e) {
    _relaxedSeen = { said: `the view could not be read (${e.message})`, view: null };
  }
}

async function refreshConfig() {
  const panel = document.getElementById('config-panel');
  try {
    const [cfgResp] = await Promise.all([fetch('/api/config'), _fetchRelaxed()]);
    const d  = await cfgResp.json();
    const az = d.azure;

    // No service-principal variables = a managed identity (the hosted VM) or az login:
    // judge by what Azure answered to this console's own reads (NSG inventory, vault),
    // not by the presence of AZURE_CLIENT_ID (a hosted Glorfindel showed "missing").
    const keyless  = !az.client_id;
    const readOk   = (_nsgItems && !_nsgItems.error) || (_backupItems && !_backupItems.error);
    const readErr  = (_nsgItems && _nsgItems.error) || (_backupItems && _backupItems.error) || '';
    const azBadge = !az.subscription_id ? '<span class="cfg-badge err">✗ AZURE_SUBSCRIPTION_ID not set</span>'
      : readOk  ? '<span class="cfg-badge ok">✓ connected</span>'
      : readErr ? `<span class="cfg-badge err" title="${_attr(String(readErr))}">✗ Azure read failed</span>`
      :           '<span class="cfg-badge">… checking</span>';

    panel.innerHTML = `
      <div class="cfg-section">
        <div class="cfg-section-title">Azure</div>
        <div class="cfg-row">
          <span class="cfg-key">status</span><span class="cfg-val">${azBadge}</span>
        </div>
        <div class="cfg-row">
          <span class="cfg-key">subscription</span><span class="cfg-val">${_attr(mask(az.subscription_id))}</span>
        </div>
        <div class="cfg-row">
          <span class="cfg-key">access</span><span class="cfg-val">${_state?.read_only
            ? '<span class="cfg-badge">👁 read-only</span> <span style="color:var(--dim)">GLORFINDEL_READ_ONLY=1</span>'
            : 'read &amp; write'}</span>
        </div>
        <div class="cfg-row">
          <span class="cfg-key">identity</span><span class="cfg-val">${keyless
            ? 'no secret — managed identity or az login'
            : 'service principal ' + _attr(mask(az.client_id)) + ' · tenant ' + _attr(mask(az.tenant_id))}</span>
        </div>
      </div>

      <div class="cfg-section">
        <div class="cfg-section-title">LLM</div>
        <div class="cfg-row">
          <span class="cfg-key">provider</span><span class="cfg-val">${_attr(d.llm.provider)}</span>
        </div>
        <div class="cfg-row">
          <span class="cfg-key">model</span><span class="cfg-val">${_attr(d.llm.model)} <span style="color:var(--dim)">${d.llm.source === 'deployment'
            ? '— set at deployment (GLORFINDEL_LLM_MODEL)'
            : '— code default (eregion_core/models.py)'}</span></span>
        </div>
        <div style="color:var(--dim);font-size:10px;padding:2px 0 4px">
          Not a setting of this page: changing the model changes who decides. Compare it first
          (<code>make llm-compare</code>), run it end to end on the bench, then set
          <code>GLORFINDEL_LLM_MODEL</code> in the deployment's environment and restart.
        </div>
        ${d.llm.base_url ? `<div class="cfg-row">
          <span class="cfg-key">base_url</span>
          <span class="cfg-val" style="color:var(--dim)">${_attr(d.llm.base_url)}</span>
        </div>` : ''}
      </div>

      <div class="cfg-section">
        <div class="cfg-section-title">Autonomy</div>
        <div class="cfg-row">
          <span class="cfg-key">default mode</span>
          <span class="cfg-val">
            <select ${_on('change', 'defaultMode')}${_state?.read_only ? ' disabled title="Observe-only (read-only credentials): human-only is locked"' : ''}
              style="font-size:11px;background:var(--bg2);border:1px solid var(--border);color:var(--text);padding:2px 6px;border-radius:3px;cursor:pointer">
              <option value="human_only"${(_state?.autonomy_default||'human_only') === 'human_only' ? ' selected' : ''}>human-only (recommend)</option>
              <option value="non_disruptive"${(_state?.autonomy_default) === 'non_disruptive' ? ' selected' : ''}>non-disruptive (execute)</option>
            </select>
          </span>
        </div>
        ${_state?.read_only ? `<div style="color:var(--blue);font-size:10px;padding:4px 0 6px">
          🔒 Locked to human-only. This console runs with read-only credentials
          (<code>GLORFINDEL_READ_ONLY=1</code> in its environment, read-only Azure rights), set when
          it was deployed for the observation. To let Glorfindel act, the deployment changes —
          write rights on the monitored resources and that variable removed — not this page.
        </div>` : ''}
        ${_state?.read_only ? '' : `<div style="color:var(--dim);font-size:10px;padding:4px 0 0">
          Per-asset overrides are set from each VM card. In non-disruptive, each VM is
          checked first: a ready VM acts alone, a VM with reserves stays in human-only
          until you confirm them.
        </div>`}
      </div>

      ${_relaxedConfig()}

      ${_sectionsConfig()}

      <div style="padding:12px 0 0;color:var(--dim);font-size:11px">
        Monitoring backends, detection rules and action backends are visible on Glorfindel's infrastructure map.
      </div>`;

  } catch (e) {
    panel.innerHTML = `<div style="color:var(--red);padding:16px">Failed to load config: ${_attr(e.message)}</div>`;
  }
}

// ── Data constants (used by infra cards) ──────────────────────────────────────

const ACTION_GROUPS = [
  { label: 'NSG',    actions: ['isolate_vm', 'block_suspicious_ip'] },
  { label: 'Backup', actions: ['restore_from_backup'] },
  { label: 'Compute',actions: ['snapshot'] },
  // P4: can the rules see this VM? Disk write counter and its cadence, Syslog, and each
  // rule that covers it — a blind VM no longer looks normal.
  { label: 'Detection', actions: ['detection'] },
];

function _worstStatus(checks, actions) {
  const relevant = checks.filter(c =>
    actions.some(a => c.action.split(/,\s*/).includes(a)));
  if (!relevant.length) return 'skip';
  if (relevant.some(c => c.status === 'fail'))  return 'fail';
  if (relevant.some(c => c.status === 'warn'))  return 'warn';
  if (relevant.every(c => c.status === 'ok'))   return 'ok';
  return 'skip';
}

// Escape what the page did not write itself — a card, a rule, a feed entry, an error:
// text from Azure, the model or a rule (#254) — for the page's text or a double-quoted
// attribute (title). Newlines → &#10; so tooltips wrap. Not a number nor a string: as text.
function _attr(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '&#10;');
}
// A segment of a route's path, from a name the page did not choose (a VM, a card's id): a `?`,
// `#` or `/` in it would change the route (SEC1).
function _seg(s) { return encodeURIComponent(String(s ?? '')); }
// A change sent to the console (SEC1): always a JSON object — the server refuses a change
// without one, or of another type; the browser adds the page's Origin, which it checks.
function _post(url, body, method = 'POST') {
  return fetch(url, { method, headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(body ?? {}) });
}
// What an element does on an event, without an inline handler (#257: script-src 'self' refuses
// them): `data-on-click="showEscModal"`, and its arguments as JSON in `data-click-args`, escaped
// like any attribute. _dispatch reads them back; the action is looked up in ACTIONS.
function _on(event, action, ...args) {
  return `data-on-${event}="${action}"` + (args.length ? ` data-${event}-args="${_attr(JSON.stringify(args))}"` : '');
}

// Full audit detail (message + fix) for a readiness group — surfaced as a tooltip
// so ✗ NSG / ✗ Backup explain WHY without going to the CLI.
function _groupDetail(checks, actions) {
  const relevant = checks.filter(c =>
    actions.some(a => c.action.split(/,\s*/).includes(a)));
  if (!relevant.length) return '';
  return relevant.map(c => {
    let s = `${c.message || c.status}`;
    if (c.fix) s += `\nFix: ${c.fix}`;
    return s;
  }).join('\n');
}

// ── Config + audit data refresh ────────────────────────────────────────────────

async function refreshCfgData() {
  try {
    const r = await fetch('/api/config');
    _cfgData = await r.json();
    renderInfra();
  } catch (e) {}
}

async function refreshAuditData() {
  if (_auditLoading) return;
  _auditLoading = true;
  renderInfra();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);
  try {
    const r = await fetch('/api/audit', { signal: ctrl.signal });
    // An answer that is not an audit is a failure, said as one (TOPO1b #949): before, an HTTP error
    // with a JSON body (a 404 or a 422 `{detail}`, a proxy's) was read as an audit without VMs, every
    // card silent. A body that is not JSON (Starlette's 500) already failed at r.json().
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    if (!Array.isArray(d?.audits)) throw new Error('the answer holds no audit');
    _auditData    = d;
    _auditLastRun = new Date().toISOString();
    _auditStale   = null;
  } catch (e) {
    const msg = e.name === 'AbortError' ? 'timeout (20s)' : e.message;
    // Resilience: keep the last good audit so a transient RSV timeout (likely with
    // 15 VMs × 3 checks) doesn't wipe every card — just flag the data stale.
    if (_auditData && Array.isArray(_auditData.audits) && _auditData.audits.length) _auditStale = msg;
    else _auditData = { audits: [], error: msg };
  } finally {
    clearTimeout(timer);
    _auditLoading = false;
    renderInfra();
  }
}

async function refreshBackups() {
  if (_backupLoading) return;
  _backupLoading = true;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);
  try {
    const r = await fetch('/api/backups', { signal: ctrl.signal });
    _backupItems = await r.json();   // {vault, items[], error?}
    _backupStale = null;
  } catch (e) {
    const msg = e.name === 'AbortError' ? 'timeout (20s)' : e.message;
    // Keep last good inventory on a transient failure; flag stale instead of wiping.
    if (_backupItems && Array.isArray(_backupItems.items) && _backupItems.items.length) _backupStale = msg;
    else _backupItems = { vault: null, items: [], error: msg };
  } finally {
    clearTimeout(timer);
    _backupLoading = false;
    renderInfra();
  }
}

async function refreshNsgs() {
  if (_nsgLoading) return;
  _nsgLoading = true;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);
  try {
    const r = await fetch('/api/nsgs', { signal: ctrl.signal });
    _nsgItems = await r.json();   // {nsgs[], error?}
    _nsgStale = null;
  } catch (e) {
    const msg = e.name === 'AbortError' ? 'timeout (20s)' : e.message;
    if (_nsgItems && Array.isArray(_nsgItems.nsgs) && _nsgItems.nsgs.length) _nsgStale = msg;
    else _nsgItems = { nsgs: [], error: msg };
  } finally {
    clearTimeout(timer);
    _nsgLoading = false;
    renderInfra();
  }
}

// ── Events (#257) ──────────────────────────────────────────────────────────────
// No handler is written into the page: an element names its action (_on), and one listener per
// event, on the document, calls it. The nearest element with an action takes the event, as the
// inline handlers' stopPropagation() did for a button inside a card. Capture phase: an action
// that stops the event (the capability popover) stops it before the document's other listeners.
// The table is closed: a name that is not in it does nothing — never a global found by its name.
let _event = null, _target = null;     // the event an action runs for, and its element

const ACTIONS = {
  confirmExtendSubnet, confirmRelease, confirmReset, confirmRestore, confirmUnblockIp, doAckAll,
  doApproveAction, doApproveRule, doRejectRule, doSnapshot, focusJudge, judgeCard, openActivation,
  openCommandModal, refreshAuditVm, refreshBackups, restorePoints, showCoverageModal, showEscModal,
  showIsolationModal, showReasoning, showRuleByIdx, toggleAsset, toggleBackend, closeModal,
  filterBlocks, showBlocks,                       // a VM's blocks, in their window (CON-K)
  verifyIdentity,                                 // an identity card's plan, read again on Graph by the watch (IR1a)
  openJudgeCard,                                  // a card's details and its verdict, from TO JUDGE or a tile (JUG1)
  copyAddr,                                       // a VM's address, copied from its card (IPS1)
  mobileTab,                                      // a phone's section, picked in its tab bar (MOB4)
  // JUG3: several cards judged at once — a box read only from the page's own checkbox.
  pickJudge(id) { if (_target instanceof HTMLInputElement && _target.type === 'checkbox') { _target.checked ? _batch.list.picked.add(id) : _batch.list.picked.delete(id); _batch.list.ask = null; _batch.list.result = null; renderToJudge(); } },
  pickAllJudge() { if (_target instanceof HTMLInputElement && _target.type === 'checkbox') { _batch.list.picked = new Set(_target.checked ? _toJudge.map(c => c.id) : []); _batch.list.ask = null; _batch.list.result = null; renderToJudge(); } },
  pickGroup(id) { if (_target instanceof HTMLInputElement && _target.type === 'checkbox') { _target.checked ? _batch.group.picked.add(id) : _batch.group.picked.delete(id); _batch.group.ask = null; _batch.group.result = null; _renderJudgeGroup(); } },
  pickGroupRule(rule) { if (_target instanceof HTMLInputElement && _target.type === 'checkbox') { const on = _target.checked; _groupJudgeable().filter(id => _batchRule(_batchCard(id)) === rule).forEach(id => on ? _batch.group.picked.add(id) : _batch.group.picked.delete(id)); _batch.group.ask = null; _batch.group.result = null; _renderJudgeGroup(); } },
  pickGroupAll() { if (_target instanceof HTMLInputElement && _target.type === 'checkbox') { _batch.group.picked = new Set(_target.checked ? _groupJudgeable() : []); _batch.group.ask = null; _batch.group.result = null; _renderJudgeGroup(); } },
  batchNote(where) { if (Object.hasOwn(_batch, where) && _target instanceof HTMLInputElement) _batch[where].note = _target.value.slice(0, 300); },
  askBatch(where, verdict) { if (!Object.hasOwn(_batch, where) || !_VERDICTS.includes(verdict)) return; const B = _batch[where]; if (!B.picked.size) return; if (_batchRunning()) { toast('⏳ A batch is being judged: wait for its end'); return; } B.ask = { verdict, note: B.note.trim(), ids: [...B.picked] }; B.result = null; _batchRender(where); },
  runBatch(where) { if (Object.hasOwn(_batch, where)) _runBatch(where); },
  cancelBatch(where) { if (Object.hasOwn(_batch, where)) { _batch[where].ask = null; _batchRender(where); } },
  clearBatch(where) { if (Object.hasOwn(_batch, where)) { Object.assign(_batch[where], { picked: new Set(), ask: null, result: null }); _batchRender(where); } },
  openJudgeGroup,                                 // a group's cards to judge, in its window (JUG3)
  openWatchCards, ackWatchCards,                  // the watch's own cards, from its node (MBV1)
  judgeFromModal(id, verdict) { judgeCard(id, verdict, 'judge-modal-note'); closeModal(); },
  confirmProposed, refuseProposed,                // VP1: a verdict proposed on an exercise card, confirmed or refused
  confirmProposedFromModal(id) { confirmProposed(id, 'judge-modal-note'); closeModal(); },
  refuseProposedFromModal(id) { refuseProposed(id); closeModal(); },
  _glowNsgVms,
  stop() {},                                      // only keeps the click from the element around
  ackAllAndClose(ids) { doAckAll(ids); closeModal(); },
  snapshotAndClose(vm) { doSnapshot(vm); closeModal(); },
  approveRuleAndClose(pid, id) { doApproveRule(pid, id); closeModal(); },
  rejectRuleAndClose(pid, id) { doRejectRule(pid, id); closeModal(); },
  approveActionAndClose(id, vm) { doApproveAction(id, vm); closeModal(); },
  approveScoped(escId, vm, scope, ip) { closeModal(); doApproveAction(escId, vm, ip ? { scope, ip } : { scope }); },
  capability(mode) { showCapabilityPopover(_event, mode); },
  // A mode is read from the page's own <select>: an element that only carries a value (an injected
  // <button value="non_disruptive">) changes nothing.
  modeChange(vm) {
    if (!(_target instanceof HTMLSelectElement)) return;
    if (_target.value === 'non_disruptive') openActivation(vm);
    else setAutonomyMode(vm, _target.value);
  },
  defaultMode() { if (_target instanceof HTMLSelectElement) setDefaultMode(_target.value); },
  dragVm(vm) {
    _event.dataTransfer.setData('text/plain', vm);
    _target.classList.add('dragging');
    document.body.classList.add('dnd');
  },
  dragEnd() {
    _target.classList.remove('dragging');
    document.body.classList.remove('dnd');
    document.querySelectorAll('.drag-over').forEach(e => e.classList.remove('drag-over'));
  },
  dragOver() { _event.preventDefault(); _target.classList.add('drag-over'); },
  dragLeave() { _target.classList.remove('drag-over'); },
  dropOn(slot) {
    _event.preventDefault();
    _target.classList.remove('drag-over');
    dropOnSlot(slot, _event.dataTransfer.getData('text/plain'));
  },
};

// mouseenter and mouseleave do not bubble: read from mouseover and mouseout, the move from one
// child to another left out.
const _EVENTS = { click: 'click', change: 'change', input: 'input', dragstart: 'dragstart', dragend: 'dragend',
                  dragover: 'dragover', dragleave: 'dragleave', drop: 'drop',
                  mouseover: 'mouseenter', mouseout: 'mouseleave' };

function _dispatch(ev, name) {
  const el = ev.target instanceof Element ? ev.target.closest(`[data-on-${name}]`) : null;
  if (!el || ((name === 'mouseenter' || name === 'mouseleave') && el.contains(ev.relatedTarget))) return;
  const action = el.getAttribute(`data-on-${name}`);
  if (!Object.hasOwn(ACTIONS, action)) return;
  let args = [];
  try { args = JSON.parse(el.getAttribute(`data-${name}-args`) || '[]'); } catch (e) { return; }
  // Names, ids, indexes, a flag: never an object (doApproveAction's scope would skip its window).
  if (!Array.isArray(args) || !args.every(a => a === null || ['string', 'number', 'boolean'].includes(typeof a))) return;
  _event = ev; _target = el;
  try { ACTIONS[action](...args); } finally { _event = _target = null; }
}

for (const [type, name] of Object.entries(_EVENTS)) document.addEventListener(type, ev => _dispatch(ev, name), true);
// The modal's Cancel closes it, unless a screen gives it its own action (openActivation).
document.getElementById('modal-cancel').onclick = closeModal;

// ── Init ───────────────────────────────────────────────────────────────────────

(async function init() {
  _showMobileTab();          // a phone: the infra until the cards to judge are read (MOB4)
  await refreshCfgData();     // detection rules + known resources → renderInfra
  await refreshState();       // active incidents → renderInfra
  if (_IS_CONFIG) toggleConfig();   // /config: this page, opened on its configuration
  else if (new URLSearchParams(location.search).has('watch')) openWatchCards();   // MBV1: from the header's pill
  await refreshObservation();
  connectWS();
  setInterval(refreshObservation, 30000);  // cards to judge + the week's count
  setInterval(refreshCfgData,   30000);  // rules polling status
  setInterval(refreshAuditData, 300000); // backup/compute readiness (slow, Azure API)
  setInterval(refreshBackups,   300000); // vault inventory for RECOVER (slow, Azure API)
  setInterval(refreshNsgs,      300000); // NSG inventory for PROTECT (slow, Azure API)
  refreshAuditData();                    // first audit in background
  refreshBackups();                      // first vault inventory in background
  refreshNsgs();                         // first NSG inventory in background
})();
