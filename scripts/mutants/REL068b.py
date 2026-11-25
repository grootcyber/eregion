"""REL068b (the 0.6.8 release gate, again red, 26/11, run 45708876393, 2 000 sequences): an L1 of the product. A
perimeter pair read on an NSG the customer took off its subnet is said on a card of the block (`perimeter_off`,
RSM3) and marked said for that NSG (`perimeter_off_said`); the operator acknowledges the card; the VM is then
blocked again, whole — a new block, a new episode (docs/design/reaffirmation.md, « épisode » ; L1Q, #363). The
block's write dropped the other drift marks but kept that one, and every pass after read « said for this NSG »:
the pair still named, still gone, never said again. M7741 keeps the mark across a block written whole again.
Measured by the two frozen sequences of tests/unit/test_invariant_regressions.py (the gate's, reduced to three
steps, and its primitive form in both modes)."""
_ST = "glorfindel/response/state.py"
_GATE = "tests/unit/test_invariant_regressions.py::test_the_068_gate_"

MUTANTS = [
    ("M7741", "a block written whole again keeps the mark of its pair said off its subnet (`perimeter_off_said`): "
              "the card acknowledged, the pair still gone is never said again (the 0.6.8 gate, L1)",
     _ST, '        if not partial:\n            prev.pop("perimeter_off_said", None)\n', ''),
]
TESTS = {
    "M7741": (f"{_GATE}a_block_written_again_says_its_pair_still_off_the_subnet "
              f"{_GATE}an_acknowledged_pair_off_its_subnet_is_said_again_once_blocked_again"),
}
