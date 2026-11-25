"""GRP1 (#1189): the infrastructure map grouped by subscription or by resource group, and what is out of reach
(Jonathan, 25/11, on a mockup, option B). Each mutant takes a piece back: the choice not kept in the browser
(M7651), a stored value not of the list taken (M7652), a tile said out of reach when the watch's
subscription is unknown (M7653), a subscription compared with its case (M7654), the watch's lane not first
after the tenant (M7655), a line from PROTECT onto a tile out of reach (M7656), its buttons that write in
Azure kept (M7657), a lane never named by SUBN1 (M7658). M7651–M7658, measured by
tests/unit/test_console_groups.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"
GR_JS = "eregion_console/static/infra_groups.js"

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
    ("M7655", "the watch's subscription not first after the tenant: its lane among the others (GRP1)", GR_JS,
     "             own: mine, out, rank: mine ? 1 : 2,", "             own: mine, out, rank: 2,"),
    ("M7656", "a line from PROTECT onto a tile out of reach: the watch would act there (GRP1)", GF_JS,
     "    // both side by side.\n    if (nbNsg && reach) {", "    // both side by side.\n    if (nbNsg) {"),
    ("M7657", "the buttons that write in Azure kept on a tile out of reach (GRP1)", GF_JS,
     "  list.querySelectorAll('.node-asset.oor').forEach(_dropWrites);", ""),
    ("M7658", "a lane never named by SUBN1: its masked id only (GRP1)", GR_JS,
     "    const sub = n.name || p.sub;", "    const sub = p.sub;"),
]

TESTS = {
    "M7651": f"{_T}test_the_choice_kept_in_the_browser_and_a_storage_that_fails_said_by_nothing",
    "M7652": f"{_T}test_the_choice_kept_in_the_browser_and_a_storage_that_fails_said_by_nothing",
    "M7653": f"{_T}test_out_of_reach_is_another_subscription_than_the_watch_s",
    "M7654": f"{_T}test_out_of_reach_is_another_subscription_than_the_watch_s",
    "M7655": f"{_T}test_by_subscription_the_tenant_the_watch_s_the_others_the_unknown",
    "M7656": f"{_T}test_no_line_from_protect_onto_a_tile_out_of_reach",
    "M7657": f"{_T}test_a_tile_out_of_reach_says_it_and_offers_nothing_to_write",
    "M7658": f"{_T}test_a_lane_named_by_subn1_else_by_its_masked_id",
}
