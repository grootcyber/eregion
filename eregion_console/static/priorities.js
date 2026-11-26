// CRT1 (#1215; docs/design/classification.md §7, Q2, Q4): a VM's priority shown — on its tile, beside its mode,
// and in the page Config (« Priorities »). The priority sets what Glorfindel spends on a VM (the model budget's
// reserve, for `essential`) and its rank in the queues of the calls to the model; never what it detects nor what
// it does alone: no link with the mode, the combination said (`ESSENTIAL · NON-DISRUPTIVE`), never corrected.
// - `essential`: a mark in capitals, a thin line around it, never filled, never an alarm colour (no --red,
//   --orange nor --yellow); `standard`: nothing, the default makes no noise; `quiet`: lower case, in --dim.
// - What the server says (/api/state `priority_levels`, /api/config `glorfindel_config.priorities`) is read by
//   `level_of` and the budget's own reckoning there; here, only written — escaped by `_attr` (glorfindel.js).
// - Read only: no button, no write; the priority is set in the config file until the signed queue (CFG5).
// Plain functions, run as they are by the suite (tests/unit/test_console_priorities.py, tests/unit/js_engine.py).

const _PRIORITY_TIP = {
  essential: 'Essential (priority): its grave detections keep part of the model budget\'s reserve. It changes '
    + 'nothing to what Glorfindel detects; what it does changes only when the model budget is tight, through '
    + 'this reserve.',
  quiet: 'Quiet (priority): this VM matters little to you. A label only: Glorfindel watches, decides and spends '
    + 'on it as on any standard VM.',
};
const _PRIORITY_SAID = {
  essential: 'its grave detections keep the model budget\'s reserve',
  quiet: 'shown quiet: same rules, same budget',
};
const _PRIORITY_CFG_NOTE = 'Set in the config file for now; the console will write it with the signed queue (CFG5).';

// The level of a VM the server read (`priority_levels`: only those not standard) — standard otherwise.
function _priorityOf(levels, vm) {
  const l = (levels && typeof levels === 'object') ? levels[vm] : '';
  return l === 'essential' || l === 'quiet' ? l : 'standard';
}

// The tile's mark, the mode beside it (`modeHtml`, the page's own badge): `ESSENTIAL · <mode>`, `quiet · <mode>`,
// the mode alone for standard. One piece that never wraps between the level and the mode (the phone, §7.4).
function _priorityMark(level, modeHtml) {
  if (level !== 'essential' && level !== 'quiet') return modeHtml;
  const [cls, word] = level === 'essential' ? ['essential', 'ESSENTIAL'] : ['quiet', 'quiet'];
  return `<span class="prio-combo"><span class="prio-mark ${cls}" title="${_attr(_PRIORITY_TIP[cls])}">${word}</span>`
    + `<span class="prio-sep">·</span>${modeHtml}</span>`;
}

// The line unfolded on an expanded tile: the effect, nothing more (a phone has no tooltip).
function _priorityLine(level) {
  if (level !== 'essential' && level !== 'quiet') return '';
  const [cls, word] = level === 'essential' ? ['essential', 'ESSENTIAL'] : ['quiet', 'quiet'];
  return `<div class="prio-line ${cls}">${word}: ${_attr(_PRIORITY_SAID[cls])}</div>`;
}

function _prioUsd(v) { return typeof v === 'number' && isFinite(v) ? `${v.toFixed(2)} $` : '?'; }

function _priorityRow(level, e) {
  const reason = e.reason ? `“${_attr(e.reason)}”` : '<span style="color:var(--dim)">(no reason)</span>';
  return `<div class="cfg-row prio-row">
      <span class="cfg-key">${_attr(e.match)}</span>
      <span class="cfg-val"><span class="prio-level ${_attr(level)}">${_attr(level)}</span> · ${reason}
        <span style="color:var(--dim)">· ${_attr((e.designates || {}).said || '')}</span></span>
    </div>`;
}

// The note of the former format (PRI2a: `autonomy:`, `critical: true`), at the head of the page Config: the watch's
// own words (/api/config `assets_notes`, empty for a file in `assets:`), the command in them.
function _assetsNotes(g) {
  const notes = Array.isArray(g && g.assets_notes) ? g.assets_notes : [];
  if (!notes.length) return '';
  return `<div class="cfg-section prio-notes">${notes.map(n => `<div class="prio-note">note · ${_attr(n)}</div>`).join('')}</div>`;
}

// The section « Priorities » of the page Config (§7.2), from /api/config's `glorfindel_config`: the entries by
// level, the reserve the essential ones keep (the server's figures, the budget's own reckoning: never one
// computed here), the essential VMs that may be isolated on their own.
function _prioritiesConfig(g) {
  return `<div class="cfg-section">
      <div class="cfg-section-title">Priorities</div>
      ${_prioritiesBody((g && g.priorities) || null)}
      <div style="color:var(--dim);font-size:10px;padding:4px 0 0">
        Read-only: the cost and the order of the calls to the model, never what Glorfindel detects nor what it
        does alone. ${_attr(_PRIORITY_CFG_NOTE)}
      </div>
    </div>`;
}

function _prioritiesBody(p) {
  if (!p) return '<div style="color:var(--dim);font-size:11px">Not read: the config could not be read.</div>';
  if (p.error) return `<div class="relaxed-warn">⚠ the priorities could not be read (${_attr(p.error)})</div>`;
  const lv = p.levels || {};
  const ess = Array.isArray(lv.essential) ? lv.essential : [];
  const quiet = Array.isArray(lv.quiet) ? lv.quiet : [];
  const std = Array.isArray(lv.standard) ? lv.standard : [];
  const r = p.reserve || {};
  const head = (t, n) => `<div class="prio-head">${t} · ${Number(n)} entr${Number(n) === 1 ? 'y' : 'ies'}`;
  const rows = [];
  if (ess.length) {
    rows.push(`${head('essential', ess.length)} · graves' reserve ${_attr(_prioUsd(r.usd))} (${_attr(_prioUsd(r.floor_usd))} floor + `
      + `${_attr(_prioUsd(r.essential_usd))} for these VMs)</div>`, ...ess.map(e => _priorityRow('essential', e)));
  }
  if (quiet.length) {
    rows.push(`${head('quiet', quiet.length)} · a label only: watched, decided and budgeted as standard</div>`,
      ...quiet.map(e => _priorityRow('quiet', e)));
  }
  if (std.length) {
    rows.push(`${head('standard', std.length)} · written as the default: an exception to a pattern's level</div>`,
      ...std.map(e => _priorityRow('standard', e)));
  }
  rows.push(rows.length ? '<div class="prio-head">standard · every other VM (the default)</div>'
    : '<div class="prio-head">none · every VM standard (the default)</div>');
  const iso = Array.isArray(p.isolable) ? p.isolable : [];
  rows.push(`<div class="cfg-row prio-iso"><span class="cfg-key">isolated on their own</span>`
    + `<span class="cfg-val">${iso.length ? iso.map(i => _attr(i.said)).join('<br>') : 'none'}</span></div>`);
  if (p.discovery) rows.push(`<div class="relaxed-warn">⚠ ${_attr(p.discovery)}: what a pattern designates is not known</div>`);
  return rows.join('');
}
