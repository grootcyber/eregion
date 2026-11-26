"""GRP1 (#1189): the infrastructure map grouped by subscription or by resource group, and what is out of reach
(Jonathan, 25/11, on a mockup, option B). Each mutant takes a piece back: the choice not kept in the browser
(M7651), a stored value not of the list taken (M7652), a tile said out of reach when the watch's
subscription is unknown (M7653), a subscription compared with its case (M7654), the watch's lane not first
among the lanes that hold a VM (M7655), a line from PROTECT onto a tile out of reach (M7656), its buttons that write in
Azure kept (M7657), a lane never named by SUBN1 (M7658); the relecture of GRP1: the watch's subscription
read from its tenant (M7702), « Review & turn on » kept on a tile out of reach (M7703), a vault's fixed line
onto it (M7704), two subscriptions of one name said alike (M7705). M7651–M7658 and M7702–M7705, measured by
tests/unit/test_console_groups.py. OCT1 (#1240) took off M7656: the tiles' edges gone, the 360° holds its rule
(SKY1's M7906); M7704 moved onto the 360°'s line from the vault.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"
GR_JS = "eregion_console/static/infra_groups.js"
SK_JS = "eregion_console/static/infra_sky.js"

_T = "tests/unit/test_console_groups.py::"

MUTANTS = [
    ("M7651", "the choice of grouping not kept in the browser: none again at each visit (GRP1)", GR_JS,
     "    try { storage().setItem(KEY, mode); return true; }", "    try { return true; }"),
    ("M7652", "a stored value not of the list taken as a grouping (GRP1)", GR_JS,
     "return MODES.includes(g) ? g : 'none'; }", "return g || 'none'; }"),
    ("M7653", "a tile said out of reach when the watch's subscription is unknown (GRP1)", GR_JS,
     "    return !!(own(watch) && p.sub && p.sub !== own(watch));", "    return !!(p.sub && p.sub !== own(watch));"),
    ("M7654", "a subscription compared with its case: the watch's own VM out of reach (GRP1)", GR_JS,
     "    if (m) return { tenant: false, sub: mask(m[1]).toLowerCase(), rg: m[2] || '' };",
     "    if (m) return { tenant: false, sub: mask(m[1]), rg: m[2] || '' };"),
    ("M7655", "the watch's subscription not first among the lanes that hold a VM: its lane among the others (GRP1)", GR_JS,
     "             own: mine, out, rank: mine ? 1 : 2,", "             own: mine, out, rank: 2,"),
    ("M7657", "the buttons that write in Azure kept on a tile out of reach (GRP1)", GF_JS,
     "  list.querySelectorAll('.node-asset.oor').forEach(_dropWrites);", ""),
    ("M7658", "a lane never named by SUBN1: its masked id only (GRP1)", GR_JS,
     "    const sub = n.name ? (twice.has(n.name.toLowerCase()) ? `${n.name} (${p.sub})` : n.name) : p.sub;",
     "    const sub = p.sub;"),
    ("M7702", "the watch's subscription read from its tenant: every tile of another subscription in reach (GRP1, its relecture)", GF_JS,
     "function _watchSub() { return String(_cfgData?.azure?.subscription_id || ''); }",
     "function _watchSub() { return String(_cfgData?.azure?.tenant_id || ''); }"),
    ("M7703", "« Review & turn on » kept on a tile out of reach: a mode it cannot act in (GRP1, its relecture)", GF_JS,
     "const _OOR_DROPS = [..._WRITE_HANDLERS, 'openActivation'];", "const _OOR_DROPS = [..._WRITE_HANDLERS];"),
    ("M7704", "a vault's fixed line onto a tile out of reach, read by its name alone (GRP1, its relecture; OCT1: in the 360°)", SK_JS,
     "    else if (all && !t.out && s.r === 'protected' && !waitsFrom('vault')) out.push(",
     "    else if (all && s.r === 'protected' && !waitsFrom('vault')) out.push("),
    ("M7705", "two subscriptions of one name: two lanes said alike (GRP1, its relecture)", GR_JS,
     "    const sub = n.name ? (twice.has(n.name.toLowerCase()) ? `${n.name} (${p.sub})` : n.name) : p.sub;",
     "    const sub = n.name || p.sub;"),
]

TESTS = {
    "M7651": f"{_T}test_the_choice_kept_in_the_browser_and_a_storage_that_fails_said_by_nothing",
    "M7652": f"{_T}test_the_choice_kept_in_the_browser_and_a_storage_that_fails_said_by_nothing",
    "M7653": f"{_T}test_out_of_reach_is_another_subscription_than_the_watch_s",
    "M7654": f"{_T}test_out_of_reach_is_another_subscription_than_the_watch_s",
    "M7655": f"{_T}test_by_subscription_the_vms_lanes_first_the_watch_s_the_others_the_unknown_then_the_tenant",
    "M7657": f"{_T}test_a_tile_out_of_reach_says_it_and_offers_nothing_to_write",
    "M7658": f"{_T}test_a_lane_named_by_subn1_else_by_its_masked_id",
    "M7702": f"{_T}test_the_page_reads_the_watch_s_subscription_where_config_puts_it",
    "M7703": f"{_T}test_out_of_reach_takes_off_the_writes_and_the_activation_never_the_verdicts",
    "M7704": f"{_T}test_no_fixed_line_from_recover_onto_a_tile_out_of_reach",
    "M7705": f"{_T}test_two_subscriptions_of_one_name_never_two_lanes_said_alike",
}
