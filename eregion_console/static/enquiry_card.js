// ENQ5b (#1284): what a card says of its cycle's enquiry (GLORFINDEL_ENQUIRY=loop) — each hypothesis of the
// technique's sheet, its state in the base, its verdict on this cycle and what settled it (the code's predicate,
// the model's citation the code checked, or nothing); each read with its state (a read not served said so, never
// « empty »); the gaps that held a disruptive action. The card's `enquete` field is written by the watch
// (glorfindel/enquiry/decision.py, `carte`); a card without it (`fixed`) shows nothing here.
// Nothing from the outside is written raw: every field through _attr (glorfindel.js), the counts through Number.

function _enquiryOf(e) {
  const q = e && e.enquete;
  return q && typeof q === 'object' && Array.isArray(q.hypotheses) ? q : null;
}

function _enquiryVerdictColor(v) {
  return v === 'confirme' ? 'var(--red)' : v === 'infirme' ? 'var(--green)' : 'var(--dim)';
}

function _enquiryHypothesis(h) {
  const reads = Array.isArray(h.lectures) && h.lectures.length
    ? ` · read in ${h.lectures.slice(0, 10).map(r => _attr(r)).join(', ')}` : '';
  return `<div style="font-size:10px;line-height:1.5;margin-top:2px" title="${_attr(h.enonce)}">`
    + `<b>${_attr(h.id)}</b> <span style="color:var(--dim)">[${_attr(h.etat)} · ${_attr(h.effet)}]</span> — `
    + `<span style="color:${_enquiryVerdictColor(String(h.verdict || ''))}">${_attr(h.verdict)}</span>`
    + ` <span style="color:var(--dim)">· settled by: ${_attr(h.par)}${reads}</span></div>`;
}

function _enquiryRead(x) {
  const state = x.servie === false ? 'not served yet' : String(x.etat || '?');
  const who = x.d_office ? 'the code' : 'the model';
  return `<span title="${_attr(x.why)}">${_attr(x.id)}: ${_attr(state)} <span style="color:var(--dim)">(${_attr(who)})</span></span>`;
}

function _enquiryNote(e) {
  const q = _enquiryOf(e);
  if (!q) return '';
  const hyps = q.hypotheses.slice(0, 12);
  const reads = (Array.isArray(q.lectures) ? q.lectures : []).slice(0, 20);
  const gaps = Array.isArray(q.trous) && q.trous.length
    ? ` · gaps: ${q.trous.slice(0, 10).map(g => _attr(g)).join(', ')}` : '';
  const cited = q.citees ? '' : ' · the model cited no hypothesis';
  const floor = q.plancher
    ? `<div style="font-size:10px;color:var(--yellow);margin-top:3px">${_attr(q.plancher)}</div>` : '';
  const ref = q.reference && typeof q.reference === 'object'
    ? `<div style="font-size:10px;color:var(--dim);margin-top:3px">last enquiry on this VM and rule: ${_attr(q.reference.date)} · decision ${_attr(q.reference.decision || '—')} · human verdict ${_attr(q.reference.verdict_humain || 'none')} (history, never the VM's state)</div>` : '';
  return `<details class="esc-context" style="margin:4px 0">`
    + `<summary style="cursor:pointer">🔎 enquiry ${_attr(q.fiche || 'base')} · ended ${_attr(q.fin || '?')}`
    + ` · ${Number(q.tours) || 0} turn(s) · ${Number(hyps.length)} hypothesis(es)${gaps}${cited}</summary>`
    + `${hyps.map(_enquiryHypothesis).join('')}`
    + `<div style="font-size:10px;margin-top:3px">reads — ${reads.map(_enquiryRead).join(' · ') || 'none'}</div>`
    + `${floor}${ref}</details>`;
}
