"""HY2 (#769): the suite never touches the operator's real ~/.glorfindel, even on a workstation — HOME a
throwaway folder from the conftest's import (M5015), a pytest a test starts with a HOME of its own
making its own (M5016), refused when a module of the repository was imported first (M5019); the
guard of the operator's folder where it exists: the test process's writes there (M5017), a write by a
subprocess failed unless a live Glorfindel's heartbeat moved (M5018). M5015–M5019, measured by
tests/unit/test_home_sandbox.py. None of them leaves a throwaway HOME behind in /tmp (a mutant that
kept `leave` from removing it would, one per round: its removal is held by
test_enter_makes_a_throwaway_home_and_leave_removes_it_never_what_it_links and the guard's runs).

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
SANDBOX = "tests/unit/home_sandbox.py"
CONFTEST = "tests/unit/conftest.py"
T = "tests/unit/test_home_sandbox.py::"

MUTANTS = [
    ("M5015", "HOME left the operator's: a path computed from it, an undone monkeypatch's, names the real "
              "~/.glorfindel again (HY2, the defect back)", SANDBOX,
     '    environ["HOME"] = str(home)\n',
     ""),
    ("M5016", "a pytest started with a HOME of its own keeps it, the throwaway HOME it inherited taken as "
              "already set: its writes go to that HOME (HY2)", SANDBOX,
     "    if mine and real and mine == current and os.path.isdir(mine):\n",
     "    if mine and real and os.path.isdir(mine):\n"),
    ("M5017", "the test process's writes in the operator's ~/.glorfindel no longer watched: a test that "
              "writes there is not named (HY2)", CONFTEST,
     "        if _store_watching[0]:   # HY2: the operator's ~/.glorfindel, wherever the suite runs\n",
     "        if False:\n"),
    ("M5018", "a live Glorfindel seen at every session: a subprocess's write in the operator's folder is "
              "only said, never failed (HY2)", SANDBOX,
     "    return any(before.get(rel) != after.get(rel) for rel in HEARTBEATS if rel in before or rel in after)\n",
     "    return True\n"),
    ("M5019", "a module of the repository imported before the throwaway HOME: its paths name the real "
              "HOME, and nothing says so (HY2)", SANDBOX,
     "    if early:\n",
     "    if False:\n"),
]
GUARD = T + "test_the_guard_fails_a_run_that_writes_in_an_operator_s_store_and_only_then"
TESTS = {
    "M5015": f"{T}test_this_session_s_home_is_a_throwaway_folder_never_the_operator_s {GUARD}",
    "M5016": T + "test_a_home_of_its_own_is_the_operator_s_whatever_was_inherited",
    "M5017": GUARD,
    "M5018": f"{T}test_a_live_glorfindel_is_told_by_its_heartbeats {GUARD}",
    "M5019": T + "test_a_module_of_the_repository_imported_first_stops_the_session",
}
