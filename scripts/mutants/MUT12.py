"""MUT12 (#834): M32, the mutant the second gate of the 0.5.13 saw caught on one round of two (run
43610485646, shard 2, seed 345556957): an outbound allow before a block counted as mere exposure. Its
target was the invariant machine alone, which meets its defect by chance only — a block on a threat's
port, then an outbound allow placed before our outbound deny (a customer's, or a rule of ours turned or
moved) on a way the attacker's flows take, then a verification or a reassertion that judges it: none in
the 500 sequences of seed 345556957 (replayed here: FIXED-ONLY, the frozen sequences catch it), the
13th step of the first falsifying sequence on 345556958 (`turned_perimeter_left_out`, the threat on 22,
the reassertion saying Db--01's block holds while db-nic-0 reaches the attacker). The frozen sequences
that name its defect, which its target did not run, added to it (TESTS_ALSO): a block's outbound deny
moved behind an allow-all out (verify_block_ip), the ways out a turned rule opens past the perimeter
(I3X, the reassertion), and a block moved behind an allow out on 443, a port the threat does not name.
Its own mutant, M5371: M32's property under another form — an outbound allow judged by the threat's port,
as an inbound one, only the last of the three catches it.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
NSG = "glorfindel/providers/azure/nsg.py"
_R = "tests/unit/test_invariant_regressions.py::"
_OTHER_PORT = f"{_R}test_a_block_moved_behind_an_allow_out_on_another_port_is_bypassed"

MUTANTS = [
    ("M5371", "an outbound allow before a block judged by the threat's port, as an inbound one: an allow out on "
     "443 before a block of a threat on 22 counted as exposure, « bloquée » while the VM reaches the attacker "
     "(MUT12, M32's property)", NSG,
     '                    port is None or direction == "outbound" or _rule_covers_port(r, port)),',
     '                    port is None or _rule_covers_port(r, port)),'),
]
TESTS = {"M5371": _OTHER_PORT}
TESTS_ALSO = {
    "M32": f"{_R}test_a_block_moved_behind_a_customer_allow_is_bypassed "
           f"{_R}test_a_way_out_a_turned_rule_opens_past_the_perimeter_is_said_unblocked {_OTHER_PORT}",
}
