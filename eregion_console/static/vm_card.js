// SKY10 (#1290; Jonathan 27/11, on a mockup, one question at a time): a VM's tile unfolded — in the sky's card as in
// the table, one tile — read from the top: its priority and its mode, as menus; its identity, one click copies a value;
// its checks, Backup, Compute, Detection, NSG; the network summed up on the NSG row, unfolded in a table (a NIC a row:
// its NSG and where it sits, its addresses, one click copies one), the table scrolling past five NICs. The tile folded
// is as before. Everything from Azure or the server goes through _attr (glorfindel.js); the counts through Number.
// Plain functions on the page's globals (_attr, _on, _addrBtn, _pubAddr, _relTime, _PRIORITY_TIP), run as they are by
// tests/unit/test_console_vm_card.py.

const _vmNetFolded = new Set();    // the tiles whose network is folded, kept across renders (unfolded at first: Ctrl+F finds an address, IPS1)

// The priority (read only until CFG5: it is set by hand in the config file) and the mode (modeChange), at the top.
function _vmCtl(vm, priority, mode, readOnly, holdChip) {
  const level = priority === 'essential' || priority === 'quiet' ? priority : 'standard';
  const prio = ['essential', 'standard', 'quiet']
    .map(l => `<option value="${l}"${l === level ? ' selected' : ''}>${l === 'essential' ? 'ESSENTIAL' : l}</option>`).join('');
  const tip = `${_PRIORITY_TIP[level] || 'Standard (priority): the default — the model reads its detections in their turn.'} ${_PRIORITY_CFG_NOTE}`;
  const act = mode === 'non_disruptive';
  const lock = readOnly ? ' disabled title="Observe-only (read-only credentials): human-only is locked"' : ' title="What Glorfindel may do alone on this VM"';
  return `<div class="vm-ctl">`
    + `<select class="vm-prio ${_attr(level)}" aria-label="Priority" disabled title="${_attr(tip)}">${prio}</select>`
    + `<select class="vm-mode${act ? ' act' : ''}" aria-label="Mode" ${_on('change', 'modeChange', vm)} ${_on('click', 'stop')}${lock}>`
    + `<option value="human_only"${act ? '' : ' selected'}>👁 human-only (recommend)</option>`
    + `<option value="non_disruptive"${act ? ' selected' : ''}>⚡ non-disruptive (execute)</option></select>`
    + `<button type="button" class="vm-cap" ${_on('click', 'capability', act ? 'non_disruptive' : 'human_only')} title="What this mode allows">ⓘ</button>`
    + (holdChip || '')
    + `<span class="vm-lock" title="${_attr(_PRIORITY_CFG_NOTE)}">🔒 priority set by hand</span>`
    + `</div>`;
}

// Its identity, the grid's first rows: Group, Subscription, Resource id — the value is the button (copyAddr, VMI1).
function _vmIdRows(v) {
  const row = (k, val, one) => val
    ? `<span class="vm-k">${k}</span><button type="button" class="vm-ip vm-full${one ? ' vm-one' : ''}" ${_on('click', 'copyAddr', val)} title="${_attr(`Copy the ${k.toLowerCase()}${one ? ': ' + val : ''}`)}">${_attr(val)}</button>`
    : '';
  return [row('Group', v.rg), row('Subscription', v.sub), row('Resource id', v.id, true)].join('');
}

// A check's row: its mark and name (its status, its detail on hover), what it says, its gesture.
function _vmCheckRow(label, st, detail, said, gesture) {
  const [ic, cls] = st === 'ok' ? ['✓', 'ok'] : st === 'warn' ? ['⚠', 'warn'] : st === 'fail' ? ['✗', 'fail'] : ['—', 'none'];
  return `<span class="vm-c ${cls}" title="${_attr(`${label}: ${st || 'not read'}${detail ? '\n' + detail : ''}`)}">${ic} ${_attr(label)}</span>`
    + `<span class="vm-d">${said || ''}</span><span class="vm-g">${gesture || ''}</span>`;
}

// The network summed up: its NSGs (each counted once), its NICs, its addresses, the shared NSGs, the NICs without
// one — what the NSG row says folded or not. null: nothing read.
function _vmNetCount(net) {
  if (!net || net.unread) return null;
  const nsgs = new Set(), shared = new Set();
  let ips = 0, bare = 0;
  for (const n of net.nics) {
    if (n.bare) bare++;
    else if (n.nsg) { nsgs.add(n.nsg); if (n.scope === 'subnet') shared.add(n.nsg); }
    ips += n.ips.length + n.pubs.length;
  }
  return { nsgs: nsgs.size, nics: net.nics.length, ips, shared: shared.size, bare };
}
function _vmNetSaid(net) {
  if (!net) return '';
  if (net.unread) return `<span class="vm-dim">addresses not read — ${_attr(net.unread)}</span>`;
  const c = _vmNetCount(net), s = (k, w) => `${Number(k)} ${w}${k === 1 ? '' : 's'}`;
  const parts = [s(c.nsgs, 'NSG'), s(c.nics, 'NIC'), s(c.ips, 'IP')];
  if (c.shared) parts.push(`<span class="vm-shared">${Number(c.shared)} shared</span>`);
  if (c.bare) parts.push(`<span class="vm-bare-txt">${s(c.bare, 'NIC')} without NSG</span>`);
  if (net.failed) parts.push(`<span class="vm-bare-txt">audit failed: ${_attr(net.failed)}</span>`);
  if (net.at) parts.push(`read ${_attr(_relTime(net.at))}`);
  return parts.join(' · ');
}

// The network unfolded: a NIC a row — its name; its NSG and where it sits (on the NIC, on its subnet shared, none:
// nothing filters it, IPS2); its private addresses and its public ones (one not read said, never left out).
function _vmNetTable(net) {
  if (!net || net.unread || !net.nics.length) return '';
  const rows = net.nics.map(n => {
    const nsg = n.bare ? '<span class="vm-bare-txt">no NSG, nor on its subnet</span>'
      : n.nsg ? `${_attr(n.nsg)}<br>${n.scope === 'subnet' ? '<span class="vm-shared">subnet, shared</span>' : '<span class="vm-dim">NIC</span>'}`
      : '<span class="vm-dim">—</span>';
    const ips = [...n.ips.map(a => _addrBtn(a, false)), ...n.pubs.map(p => _pubAddr(p, true, n.bare))].join('<br>') || '<span class="vm-dim">—</span>';
    return `<span class="vm-nc">⇄ ${_attr(n.nic || 'NIC')}</span><span class="vm-ns">${nsg}</span><span class="vm-ni">${ips}</span>`;
  }).join('');
  return `<div class="vm-net-t"><span class="vm-nh">NIC</span><span class="vm-nh">NSG</span><span class="vm-nh">IP</span>${rows}</div>`;
}
function _vmNetToggle(key, open) {
  return `<button type="button" class="vm-tog" aria-expanded="${open ? 'true' : 'false'}" ${_on('click', 'toggleNet', key)}>${open ? '▾' : '▸'} network</button>`;
}
