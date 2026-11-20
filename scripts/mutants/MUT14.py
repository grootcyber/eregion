"""MUT14 (the 0.6.2 release gate): M2343 (D80, scripts/mutation_check.py) survived from SEC-H
(c4972304, #901) on.

Its text, `if t0 is None or k in views[t0["nic_id"]] or skip(k, name):` at 16 spaces, was the one
check of the search away from a bare NIC (glorfindel/providers/azure/away.py, _away_split): the NSGs
that govern the NIC are swept for it already, skipped there. SEC-H split it in two: the new names
pass `elif k in views[t0["nic_id"]] or skip(k, name):`, the older names (6 or 8 hex) a copy of the
old line indented by 20, which M2343's text, a substring of it, matches once. M2343 mutates the
older names' path since, which D80's test (a rule under the new name) never takes. No safety lost:
the new names' check holds (D80's test fails without it).

- M2343 gets a test of its path (TESTS_ALSO): an older-name pair of the bare NIC on its subnet's
  NSG, which governs the NIC — left and said once by the sweep, twice under M2343.
- M6446 measures again the new names' line, which no mutant aimed at since SEC-H: D80's test.

Range handed by the Orchestre: M6446–M6450.
"""
AWY = "glorfindel/providers/azure/away.py"
_RA = "tests/unit/test_release_away.py"

MUTANTS = [
    ("M6446", "the bare NIC's subnet NSG searched twice under the new names: its kept rule named twice "
     "(MUT14, D80's line since SEC-H)", AWY,
     '                elif k in views[t0["nic_id"]] or skip(k, name):\n',
     "                elif skip(k, name):\n"),
]
TESTS = {"M6446": f"{_RA}::test_a_rule_on_the_bare_nics_subnet_nsg_is_said_once"}
TESTS_ALSO = {"M2343": f"{_RA}::test_an_older_name_on_the_bare_nics_subnet_nsg_is_said_once"}
