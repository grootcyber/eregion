"""SKY1 (#1236): the map at 360° (Jonathan, 26/11, on a mockup). Each mutant takes a piece back: a tile of its own
orbiting a sun (M7900), the constellation lost without a grouping (M7901), the tenant's sector not at the top (M7902),
planets that never turn (M7903), satellites never grouped beyond six (M7904), a backend inside a « +N » drawn from
nowhere (M7905), PROTECT's lines onto a tile out of reach (M7906), a VM isolated and blocked said isolated only
(M7907), an action to approve drawn nowhere (M7908), a card that is not a decision drawn nowhere (M7909), a restore
drawn from the workspace (M7910), a line through Glorfindel (M7911); the page: a tile's workspace never the
discovery's (M7912), an NSG matched with its case (M7913), a vault on a VM no vault holds (M7914), an NSG that
governs nothing drawn (M7915); the review's first round: a namesake out of reach given the watch's vault (M7927) or
NSG (M7928), served by a PROTECT or RECOVER satellite (M7929), the panel written again though unchanged (M7930), the
keyboard unable to pin (M7931), the panel's writes kept on a tile out of reach (M7932), an NSG's tile matched by its
name (M7933), the large screen's default not the 360° (M7934); its second round: the panel's guards out of its
comparison (M7938), a guard that changes under a field ignored (M7939), a button's focus given back without its tile
(M7940), the tiles' focus left on in the 360° (M7941); its third round: the guard compared by its words (M7942). Measured by tests/unit/test_console_sky.py and
tests/unit/test_console_table.py. OCT1 (#1240) took off M7941: the tiles' focus gone, nothing to take off in the 360°.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
SK_JS = "eregion_console/static/infra_sky.js"
SD_JS = "eregion_console/static/infra_sky_draw.js"
TB_JS = "eregion_console/static/infra_table.js"
GF_JS = "eregion_console/static/glorfindel.js"

_T = "tests/unit/test_console_sky.py::"

MUTANTS = [
    ("M7900", "a tile of its own (Entra ID, the control plane) orbiting a sun as a planet (SKY1)", SK_JS,
     "      const orbit = l.tiles.filter(t => !t.own);", "      const orbit = l.tiles;"),
    ("M7901", "the constellation lost: without a grouping, the lanes' systems drawn (SKY1)", SK_JS,
     "    if (mode === 'none' || !lanes) {", "    if (!lanes) {"),
    ("M7902", "the tenant's sector not at the top (SKY1)", SK_JS,
     "    sectors.sort((x, y) => (x.key === 'tenant' ? -1 : y.key === 'tenant' ? 1 : 0));\n", ""),
    ("M7903", "planets that never turn (SKY1)", SK_JS,
     "    const phi = 2 * Math.PI * k / Math.max(1, body.planets.length) + OMEGA * tau + body.ang;",
     "    const phi = 2 * Math.PI * k / Math.max(1, body.planets.length) + body.ang;"),
    ("M7904", "satellites never grouped beyond six: the arc crowded (SKY1)", SK_JS,
     "    const kept = sized.length > SAT_MAX ? sized.slice(0, SAT_MAX - 1) : sized;", "    const kept = sized;"),
    ("M7905", "a backend inside a « +N » drawn from nowhere (SKY1)", SK_JS,
     "    const m = Object.keys(sats).find(k => (sats[k].more || []).includes(id));\n    return m || '';", "    return '';"),
    ("M7906", "PROTECT's lines onto a tile out of reach: the watch would act there (SKY1)", SK_JS,
     "    if (!t.out && s.p) {", "    if (s.p) {"),
    ("M7907", "a VM isolated and blocked said isolated only (SKY1)", SK_JS,
     "      if (s.p === 'blocked' || s.p === 'both') out.push({ from: from.nsg, c: 'orange' });",
     "      if (s.p === 'blocked') out.push({ from: from.nsg, c: 'orange' });"),
    ("M7908", "an action to approve drawn nowhere (SKY1)", SK_JS,
     "  const WAIT = { detect: ['law', 'blue'], isolate: ['nsg', 'red'],", "  const WAIT = { detect: ['law', 'blue'],"),
    ("M7909", "a card that is not a decision drawn nowhere (SKY1)", SK_JS,
     "                 other: ['nsg', 'purple'] };", "                 };"),
    ("M7910", "a restore drawn from the workspace, not from its vault (SKY1)", SK_JS,
     "    if (!t.out && s.r === 'restoring') out.push({ from: from.vault, c: 'green', pulse: true });",
     "    if (!t.out && s.r === 'restoring') out.push({ from: from.law, c: 'green', pulse: true });"),
    ("M7911", "a line through Glorfindel: its lane ignored (SKY1)", SK_JS,
     "    const L = lane + shift, pts = [];", "    const L = 40 + shift, pts = [];"),
    ("M7912", "a tile's workspace never the discovery's: every VM drawn from the first (SKY1)", GF_JS,
     "             law: d && d.monitoring_backend ? 'nb-' + d.monitoring_backend : dets.length ? 'nb-' + dets[0].name : '',",
     "             law: dets.length ? 'nb-' + dets[0].name : '',"),
    ("M7913", "an NSG matched to its VMs with their case: an isolation drawn from the arc (SKY1)", GF_JS,
     "  for (const n of nsgs) for (const v of (n.vms || [])) { const id = String(v || '').toLowerCase();",
     "  for (const n of nsgs) for (const v of (n.vms || [])) { const id = String(v || '');"),
    ("M7914", "a vault on a VM no vault holds (SKY1)", GF_JS,
     "             vault: !oor && !own && !r.is_nsg && held && _vmProtected(r.vm_name) === true ? 'nb-' + held : '',",
     "             vault: !oor && !own && !r.is_nsg && held ? 'nb-' + held : '',"),
    ("M7915", "an NSG that governs nothing drawn as a satellite (SKY1)", GF_JS,
     "      p: nsgs.filter(n => (n.vms || []).length).map(n => ({ id: 'nsg:' + n.nsg, name: String(n.nsg || '').split('/').pop() })),",
     "      p: nsgs.map(n => ({ id: 'nsg:' + n.nsg, name: String(n.nsg || '').split('/').pop() })),"),
    ("M7927", "a namesake out of reach given the watch's vault (SKY1, the review)", GF_JS,
     "             vault: !oor && !own && !r.is_nsg && held && _vmProtected(r.vm_name) === true ? 'nb-' + held : '',",
     "             vault: !own && !r.is_nsg && held && _vmProtected(r.vm_name) === true ? 'nb-' + held : '',"),
    ("M7928", "a namesake out of reach given the NSG of the watch's VM (SKY1, the review)", GF_JS,
     "               : !oor ? governs.get(String(r.resource_id || '').toLowerCase()) || '' : '',",
     "               : governs.get(String(r.resource_id || '').toLowerCase()) || '',"),
    ("M7929", "a tile out of reach served by a PROTECT or RECOVER satellite (SKY1, the review)", SK_JS,
     "      .some(([m, id]) => id && satOfId(id) === f.b && (m === 'd' || !t.out))).map(t => t.key));",
     "      .some(([m, id]) => id && satOfId(id) === f.b)).map(t => t.key));"),
    ("M7930", "the panel written again at each refresh though unchanged: a focus lost, a select closed (SKY1, the review)", GF_JS,
     "  if (sig === _skyPanelLast && box.childElementCount) return;                  // unchanged: nothing rewritten\n", ""),
    ("M7931", "the keyboard unable to pin a tile (SKY1, the review)", SD_JS,
     "    svg.addEventListener('keydown', ev => {", "    svg.addEventListener('keyup', ev => {"),
    ("M7932", "the panel's writes kept on a tile out of reach (SKY1, the review)", GF_JS,
     "  box.querySelectorAll('.node-asset.oor').forEach(_dropWrites);   // out of reach, nothing written\n", ""),
    ("M7933", "an NSG's tile matched by its name, not its id: its lines from the arc (SKY1, the review)", GF_JS,
     "             nsg: !oor && r.is_nsg ? nsgById.get(String(r.resource_id || '').toLowerCase()) || ''",
     "             nsg: !oor && r.is_nsg ? 'nsg:' + r.vm_name"),
    ("M7934", "the large screen's default not the 360° (SKY1, the review)", TB_JS,
     "    return phone ? 'table' : 'sky';", "    return phone ? 'table' : 'tiles';"),
    ("M7938", "the panel's guards out of its comparison: Release and Snapshot left disabled once read-only is lifted (SKY1, its second round)", GF_JS,
     "  const sig = html + '\\u0000' + guard;", "  const sig = html;"),
    ("M7939", "under a field, a guard that changes ignored: a write kept on a tile gone out of reach (SKY1, its second round)", GF_JS,
     "  if (inField && guard === _skyGuardLast) return;", "  if (inField) return;"),
    ("M7940", "a button's focus given back without its tile: a namesake's Release focused (SKY1, its second round)", GF_JS,
     "          (e.closest && e.closest('[id^=\"asset-\"]')?.id) || ''].join('|');", "          ''].join('|');"),
    ("M7942", "the guard compared by its words: a stale queue's age rewrites the panel at each refresh (SKY1, its third round)", GF_JS,
     "  const guard = JSON.stringify([!!_writesBlocked(), !!(pinned && _isOor(pinned))]);",
     "  const guard = JSON.stringify([_writesBlocked(), !!(pinned && _isOor(pinned))]);"),
]

TESTS = {
    "M7900": f"{_T}test_the_systems_follow_the_grouping_and_a_tile_of_its_own_is_a_lone_body",
    "M7901": f"{_T}test_the_systems_follow_the_grouping_and_a_tile_of_its_own_is_a_lone_body",
    "M7902": f"{_T}test_a_sector_per_subscription_the_tenant_s_at_the_top",
    "M7903": f"{_T}test_a_planet_turns_on_its_orbit_each_at_its_place",
    "M7904": f"{_T}test_beyond_six_the_smallest_satellites_go_into_one",
    "M7905": f"{_T}test_beyond_six_the_smallest_satellites_go_into_one",
    "M7906": f"{_T}test_a_line_lights_only_when_something_happens_from_the_backend_that_acts",
    "M7907": f"{_T}test_a_line_lights_only_when_something_happens_from_the_backend_that_acts",
    "M7908": f"{_T}test_a_line_lights_only_when_something_happens_from_the_backend_that_acts",
    "M7909": f"{_T}test_a_line_lights_only_when_something_happens_from_the_backend_that_acts",
    "M7910": f"{_T}test_a_line_lights_only_when_something_happens_from_the_backend_that_acts",
    "M7911": f"{_T}test_a_line_never_crosses_glorfindel_and_reaches_its_planet_without_a_jump",
    "M7912": f"{_T}test_the_page_gives_each_tile_its_log_source_its_nsg_and_its_vault",
    "M7913": f"{_T}test_the_page_gives_each_tile_its_log_source_its_nsg_and_its_vault",
    "M7914": f"{_T}test_the_page_gives_each_tile_its_log_source_its_nsg_and_its_vault",
    "M7915": f"{_T}test_the_page_gives_the_lanes_the_sectors_and_the_backends",
    "M7927": f"{_T}test_the_page_gives_each_tile_its_log_source_its_nsg_and_its_vault",
    "M7928": f"{_T}test_the_page_gives_each_tile_its_log_source_its_nsg_and_its_vault",
    "M7929": f"{_T}test_out_of_reach_protect_and_recover_serve_nothing_detect_still_does",
    "M7930": f"{_T}test_the_panel_is_written_only_when_it_changes_never_under_a_field_and_out_of_reach_writes_nothing",
    "M7931": f"{_T}test_the_keyboard_pins_as_a_click_and_sees_where_it_is",
    "M7932": f"{_T}test_the_panel_is_written_only_when_it_changes_never_under_a_field_and_out_of_reach_writes_nothing",
    "M7933": f"{_T}test_the_page_gives_each_tile_its_log_source_its_nsg_and_its_vault",
    "M7934": "tests/unit/test_console_table.py::test_the_view_kept_in_the_browser_the_table_by_default_on_a_phone",
    "M7938": f"{_T}test_the_panel_follows_its_guards_even_under_a_field_and_gives_the_focus_back_in_its_own_tile",
    "M7939": f"{_T}test_the_panel_follows_its_guards_even_under_a_field_and_gives_the_focus_back_in_its_own_tile",
    "M7940": f"{_T}test_the_panel_follows_its_guards_even_under_a_field_and_gives_the_focus_back_in_its_own_tile",
    "M7942": f"{_T}test_the_panel_follows_its_guards_even_under_a_field_and_gives_the_focus_back_in_its_own_tile",
}
