"""SKY1 (#1236): the map at 360° (Jonathan, 26/11, on a mockup). Each mutant takes a piece back: a tile of its own
orbiting a sun (M7900), the constellation lost without a grouping (M7901), the tenant's sector not at the top (M7902),
planets that never turn (M7903), satellites never grouped beyond six (M7904), a backend inside a « +N » drawn from
nowhere (M7905), PROTECT's lines onto a tile out of reach (M7906), a VM isolated and blocked said isolated only
(M7907), an action to approve drawn nowhere (M7908), a card that is not a decision drawn nowhere (M7909), a restore
drawn from the workspace (M7910), a line through Glorfindel (M7911); the page: a tile's workspace never the
discovery's (M7912), an NSG matched with its case (M7913), a vault on a VM no vault holds (M7914), an NSG that
governs nothing drawn (M7915). Measured by tests/unit/test_console_sky.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
SK_JS = "eregion_console/static/infra_sky.js"
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
     "      if (s.p === 'blocked' || s.p === 'both') out.push({ from: nsg, c: 'orange' });",
     "      if (s.p === 'blocked') out.push({ from: nsg, c: 'orange' });"),
    ("M7908", "an action to approve drawn nowhere (SKY1)", SK_JS,
     "      if (s.a) out.push({ from: nsg, c: 'purple', wait: true });\n", ""),
    ("M7909", "a card that is not a decision drawn nowhere (SKY1)", SK_JS,
     "    if (s.d === 'judge' || s.d === 'card') out.push({ from: law, c: 'purple', wait: true });",
     "    if (s.d === 'judge') out.push({ from: law, c: 'purple', wait: true });"),
    ("M7910", "a restore drawn from the workspace, not from its vault (SKY1)", SK_JS,
     "    if (!t.out && s.r === 'restoring') out.push({ from: vault, c: 'green', pulse: true });",
     "    if (!t.out && s.r === 'restoring') out.push({ from: law, c: 'green', pulse: true });"),
    ("M7911", "a line through Glorfindel: its lane ignored (SKY1)", SK_JS,
     "    const L = lane + shift, pts = [];", "    const L = 40 + shift, pts = [];"),
    ("M7912", "a tile's workspace never the discovery's: every VM drawn from the first (SKY1)", GF_JS,
     "             law: d && d.monitoring_backend ? 'nb-' + d.monitoring_backend : dets.length ? 'nb-' + dets[0].name : '',",
     "             law: dets.length ? 'nb-' + dets[0].name : '',"),
    ("M7913", "an NSG matched to its VMs with their case: an isolation drawn from the arc (SKY1)", GF_JS,
     "  for (const n of nsgs) for (const v of (n.vms || [])) { const id = String(v || '').toLowerCase();",
     "  for (const n of nsgs) for (const v of (n.vms || [])) { const id = String(v || '');"),
    ("M7914", "a vault on a VM no vault holds (SKY1)", GF_JS,
     "             vault: !own && !r.is_nsg && held && _vmProtected(r.vm_name) === true ? 'nb-' + held : '',",
     "             vault: !own && !r.is_nsg && held ? 'nb-' + held : '',"),
    ("M7915", "an NSG that governs nothing drawn as a satellite (SKY1)", GF_JS,
     "      p: nsgs.filter(n => (n.vms || []).length).map(n => ({ id: 'nsg:' + n.nsg, name: n.nsg })),",
     "      p: nsgs.map(n => ({ id: 'nsg:' + n.nsg, name: n.nsg })),"),
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
}
