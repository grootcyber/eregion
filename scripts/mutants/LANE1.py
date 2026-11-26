"""LANE1 (#1226): the grouped map's lanes that hold a VM first (Jonathan, 26/11, on a mockup) — their lines from
PROTECT and RECOVER no longer cross the small lanes (the tenant, a subscription's own tiles). Each mutant takes a
piece back: the lanes in GRP1's order again, the tenant first (M7841), a lane of own tiles taken for one that
holds a VM (M7842). M7841–M7842, measured by tests/unit/test_console_groups.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GR_JS = "eregion_console/static/infra_groups.js"

_T = "tests/unit/test_console_groups.py::"

MUTANTS = [
    ("M7841", "the lanes in GRP1's order again: the tenant first, the VMs' lines across it (LANE1)", GR_JS,
     "    return [...by.values()].sort((a, b) => vm(a) - vm(b) || a.rank - b.rank",
     "    return [...by.values()].sort((a, b) => a.rank - b.rank"),
    ("M7842", "a lane of own tiles taken for one that holds a VM: the control plane's lane first (LANE1)", GR_JS,
     "    const vm = l => (l.tiles.some(t => !t.kind) ? 0 : 1);", "    const vm = l => (l.tiles.length ? 0 : 1);"),
]

TESTS = {
    "M7841": f"{_T}test_a_lane_without_a_vm_comes_after_every_lane_that_holds_one",
    "M7842": f"{_T}test_a_lane_without_a_vm_comes_after_every_lane_that_holds_one",
}
