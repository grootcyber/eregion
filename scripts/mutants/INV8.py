"""INV8 (#1105): I8 red at the 0.6.5 release gate (seed 152578281), an oracle's: a NIC isolated bare after
its state and our tags were lost — "no NSG" all Glorfindel could record — then left bare again while that
state held it (a reset cut short, a release cut short, someone): the oracle read that state as one that knew
our NSG had been taken off, and counted against the release an older isolation on an NSG nothing ties to the
NIC any more. A state whose placement says "no NSG" for a NIC the test's journal saw go into quarantine bare
no longer counts (`_went_in_bare`, tests/unit/test_invariants.py); the code is unchanged. What the exemption
must not swallow stays measured: a "no NSG" written where the original is unknown. M7172–M7173.
Measured (23/11): by the frozen sequences, M7172 17 of them (test_a_none_recorded_over_an_unknown_is_still_judged
among them; 9 without the journal's condition), M7173 14; by the machine alone at 60 sequences, both caught on
three seeds out of three (1, 7, 42) — by I2, I3 or I8, not by the exemption alone. M7174 (the review's C′: a known
original read as 'none' at a bare NIC's re-isolation) survived every frozen sequence and fell to the machine at 60
on one seed of three (the review's measure): caught by the review's world X, frozen
(test_a_bare_nic_whose_state_knows_its_original_is_not_isolated_as_none), the only frozen sequence to catch it.
mutation_check.py --only M7172,M7173,M7174 --jobs 2 (seed 188689183, 60 sequences, three rounds): 3/3 each.
"""
QUA = "glorfindel/providers/azure/quarantine.py"
STATE = "glorfindel/response/state.py"
_R = "tests/unit/test_invariant_regressions.py"
_I = "tests/unit/test_invariants.py"

MUTANTS = [
    ("M7172", "a NIC still in our quarantine, its state and our tags lost, isolated again: 'none' recorded in "
              "place of the unknown — left bare by someone, released bare, an older isolation on its NSG "
              "without state (INV8, Q7)", QUA,
     "                except OriginalUnknown:\n"
     "                    original = _UNKNOWN\n"
     "            if original is _UNKNOWN:\n",
     "                except OriginalUnknown:\n"
     "                    original = None\n"
     "            if original is _UNKNOWN:\n"),
    ("M7174", "a bare NIC isolated again reads the original its state knows as 'none': the release leaves it "
              "bare, its NSG off it — the exemption, which now reads the state's 'none', must not cover it "
              "(INV8, relecture: C')", QUA,
     '                recorded = prior = _recorded_or_unknown(t["nic_id"])\n',
     '                recorded = prior = _recorded_or_unknown(t["nic_id"])\n'
     '                if isinstance(prior, str):\n'
     '                    recorded = prior = None\n'),
    ("M7173", "a placement that records no original read as 'none' by the state: the unknown of a NIC left "
              "bare becomes 'no NSG to put back' (INV8, I8F)", STATE,
     '        if "original_nsg_id" in p:\n'
     '            return p["original_nsg_id"]\n',
     '        return p.get("original_nsg_id")\n'),
]

TESTS = {
    "M7172": f"{_R} {_I}",
    "M7173": f"{_R} {_I}",
    "M7174": f"{_R} {_I}",
}
