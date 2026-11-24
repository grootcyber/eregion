"""ENQ2b (#1069): the follow-ups of ENQ2's review (glorfindel/enquiry/catalog.py,
glorfindel/enquiry/fixed.py). M7103–M7106: `backup_agent_check` said provocable again, though its rows
name a process the guest names (no code reads the author yet: a test on the catalogue); the check of a
parameter skipped in `fixed`; a parameter declared without its check, accepted (M7105), or named by a read
without being declared (M7106). Measured by
tests/unit/test_enquiry_catalog.py."""
CATALOG = "glorfindel/enquiry/catalog.py"
FIXED = "glorfindel/enquiry/fixed.py"
_T = "tests/unit/test_enquiry_catalog.py"

MUTANTS = [
    ("M7103", "backup_agent_check said provocable: a process named like a backup agent forges it (ENQ2b)",
     CATALOG,
     "BACKUP_AGENT, (\"vm\",), timedelta(minutes=10), PERF_LATENCY_S, GUEST_FORGEABLE,\n",
     "BACKUP_AGENT, (\"vm\",), timedelta(minutes=10), PERF_LATENCY_S, GUEST_PROVOCABLE,\n"),
    ("M7104", "the check of a parameter skipped in fixed: the value goes to its literal unchecked (ENQ2b, "
     "SEC4c)", FIXED,
     # DOS4 (#1138): `raw` built from PARAMS, NO_OBJECT its sentinel.
     "            filled[p] = None if raw[p] is catalog.NO_OBJECT else value(catalog.PARAMS[p].check, raw[p])\n",
     "            filled[p] = None if raw[p] is catalog.NO_OBJECT else value(str, raw[p])\n"),
    ("M7105", "a parameter declared without its check, accepted (ENQ2b)", CATALOG,
     "        if not callable(self.check):\n",
     "        if False:\n"),
    ("M7106", "a read naming a parameter not declared in PARAMS, accepted (ENQ2b)", CATALOG,
     "        if undeclared := [p for p in self.params if p not in PARAMS]:\n",
     "        if False:\n"),
]

TESTS = {mid: _T for mid in ("M7103", "M7104", "M7105", "M7106")}
