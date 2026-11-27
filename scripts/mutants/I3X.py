"""I3X (#824): the night « Invariants (deep) » of 14/11, red on macOS (the same on Linux: not that
system's case-insensitive disk). api's own `-out`, beside its perimeter pair on nsg-edge, narrowed to
port 22 — or turned to UDP — then into an allow, before the perimeter's `-out`: the pass said
« l'IP n'est plus bloquée sur api-nic ». True — the VM reaches the attacker on 22 (on UDP) —, and the
oracle judged it false: « cut off on every port » read on its probes, all TCP, none out to the
attacker on 22. The oracle's defect, not the product's: it reads now every way to and from the
attacker by port and protocol (`ATTACKER_WAYS`, tests/unit/fake_azure.py), the world's NSGs evaluated.
M5331: the product's side the frozen sequence holds — an outbound allow before the perimeter's `-out`
counted as holding, the card « reste bloquée » while the VM reaches the attacker. Measured by the frozen
sequences (tests/unit/test_invariant_regressions.py) and the machine. Until I3Xb (#1035, 27/11), an outbound
allow on 22 or on UDP escaped the machine (its oracle of a held block read the probes) and, turned whole, the
machine drew it rarely (0 of 3 rounds at 60; 3 of 6 seeds at 200). Its oracle reads now every way to and from the
attacker, its rule `a_way_narrowed_then_turned` draws the state: the machine alone, the frozen sequences left
out, catches M5331 on 4 of 4 seeds at 200 (1, 2, 3, 6)."""
_PER = "glorfindel/providers/azure/perimeter.py"
_REG = "tests/unit/test_invariant_regressions.py::"
_FOUND = f"{_REG}test_a_way_out_a_turned_rule_opens_past_the_perimeter_is_said_unblocked"

MUTANTS = [
    ("M5331", "an outbound allow before the perimeter's `-out` read as holding: « l'IP reste bloquée » of a "
              "NIC whose way out to the attacker stands, on 22 or on UDP (I3X, the side the sequence holds)",
     _PER, "                if found is not None and not self._threat_open(found):\n",
     "                if found is not None and not self._threat_open(\n"
     "                        [f for f in found if f.get(\"direction\") != \"outbound\"]):\n"),
]
TESTS = {"M5331": f"{_FOUND} tests/unit/test_invariants.py"}
