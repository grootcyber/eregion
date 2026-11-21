"""G1e (Partie de #76): Gothmog arms on the base contract, EREGION_STRATUS_SUBSCRIPTION set or not —
the 20/11 bench, where the Stratus guarantees judged every arming and Gothmog fell passive (ORG1,
#1003, scopes them to an arming for Stratus). M6924–M6925, measured by tests/unit/test_gothmog.py
through the real arm() and check(), the base readers on a faked transport."""
EN = "gothmog/runner/engine.py"
_T = "tests/unit/test_gothmog.py::test_gothmog_arms_with_a_stratus_subscription_set_and_no_stratus_proof"

MUTANTS = [
    ("M6924", "gothmog preflight arms for Stratus: passive on a bench whose orodruin.env names a "
     "Stratus subscription (G1e, the 20/11 bench)", EN,
     '        verdict, session = arm(run_id, "gothmog")\n',
     '        verdict, session = arm(run_id, "gothmog", for_stratus=True)\n'),
    ("M6925", "gothmog run arms for Stratus: passive on a bench whose orodruin.env names a Stratus "
     "subscription (G1e, the 20/11 bench)", EN,
     '        verdict, session = arm(run_id, "gothmog", request=request)\n',
     '        verdict, session = arm(run_id, "gothmog", request=request, for_stratus=True)\n'),
]

TESTS = {
    "M6924": _T,
    "M6925": _T,
}
