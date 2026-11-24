"""CFG3b (#1148): the view « Relaxed » shows a backend's discovery cut (glorfindel/relaxed.py,
eregion_console/static/glorfindel.js). M7355–M7357: a backend whose discovery is on shown as cut; the discovery
line shown whatever CFG4's class; a key that tightens (`sensitive_commands`) let into the view. Measured by
tests/unit/test_relaxed_view.py."""
REL = "glorfindel/relaxed.py"
_T = "tests/unit/test_relaxed_view.py"

MUTANTS = [
    ("M7355", "a backend whose discovery is on, written or by default, shown as cut (CFG3b)", REL,
     "        if backend.discovery.enabled:\n            continue\n"
     "        said = entry_class(raw, (\"monitoring_backends\", i, \"discovery\", \"enabled\"), full)\n",
     "        said = entry_class(raw, (\"monitoring_backends\", i, \"discovery\", \"enabled\"), full)\n"),
    ("M7356", "the discovery cut shown whatever CFG4's class says: the view no longer follows classify (CFG3b)", REL,
     "        if said[\"class\"] != \"relax\":\n            continue\n"
     "        # No reason: a backend carries none",
     "        # No reason: a backend carries none"),
    ("M7357", "a key that tightens let into the view: each `expected_sudo.sensitive_commands` a line (CFG3b)", REL,
     "((\"exceptions\",), \"exclusion\"), ",
     "((\"exceptions\",), \"exclusion\"), ((\"expected_sudo\", \"sensitive_commands\"), \"exposed_zone\"), "),
]

TESTS = {f"M{n}": _T for n in range(7355, 7358)}
