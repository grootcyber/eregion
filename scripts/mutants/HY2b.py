"""HY2b (#791): a probe of an agent session, outside the suite, never writes in the operator's real
~/.glorfindel — refused and said before it happens, by an audit hook eregion_core installs in an agent
session only (eregion_core/store_guard.py). M5150–M5159, measured by tests/unit/test_store_guard.py:
probes in fresh interpreters over an operator simulated in tmp (its system home a folder of tmp_path),
never this workstation's.
"""
GUARD = "eregion_core/store_guard.py"
T = "tests/unit/test_store_guard.py::"
AGENT = T + "test_an_agent_session_s_probe_is_refused_before_it_writes_and_says_so"
WORKTREE = T + "test_a_probe_from_a_lot_s_worktree_is_refused_and_said_even_when_it_swallows_the_error"
OPERATOR = T + "test_the_operator_writes_as_before"
WRITE = T + "test_a_write_is_any_opening_for_writing_and_every_change_of_the_tree_never_a_read"
PLACED = T + "test_a_path_is_placed_in_the_store_as_given_or_resolved_never_beside_it"

MUTANTS = [
    ("M5150", "the hook never installed: an agent session's probe writes in the operator's ~/.glorfindel "
              "again (HY2b, the defect of 12/11 back)", GUARD,
     "    sys.addaudithook(_hook)\n", "    pass\n"),
    ("M5151", "EREGION_AGENT_SESSION no longer read: a probe of a session launched in ~/eregion, outside a "
              "worktree, writes there (HY2b)", GUARD,
     "    if env.get(SESSION_VAR):\n", "    if False:\n"),
    ("M5152", "a lot's worktree no longer an agent session's: a session without the repository's settings "
              "writes there from its worktree (HY2b)", GUARD,
     '    if ".claude" in parts and "worktrees" in parts[parts.index(".claude"):]:\n', "    if False:\n"),
    ("M5153", "the guard installed everywhere: the operator's CLI, his containers, the watch and Imladris "
              "refused in their own ~/.glorfindel (HY2b)", GUARD,
     "    why = why_guarded(env, cwd)\n", '    why = why_guarded(env, cwd) or "partout"\n'),
    ("M5154", "a file opened to append no longer a write: a journal (vm_notices.jsonl's lock, "
              "escalations.jsonl) grows in the operator's folder (HY2b)", GUARD,
     '        writes = any(c in mode for c in "wax+")', '        writes = any(c in mode for c in "wx+")'),
    ("M5155", "a rename or a replace no longer a write: an atomic write's os.replace, a file moved out, "
              "pass (HY2b)", GUARD,
     '    "os.rename": ((0, 1), (2, 3)),          # os.replace, shutil.move on one file system\n', ""),
    ("M5156", "a path placed as given only, never resolved: a write through another link to the operator's "
              "home passes (HY2b)", GUARD,
     "    for candidate in dict.fromkeys((full, os.path.realpath(full))):\n",
     "    for candidate in (full,):\n"),
    ("M5157", "the refusal no longer said on stderr: a probe that swallows the OSError hides it (HY2b)",
     GUARD, "            sys.stderr.write(said + \"\\n\")\n", "            pass\n"),
    ("M5158", "a folder beside the store taken for it: ~/.glorfindel-old, ~/.glorfindel2 refused (HY2b)",
     GUARD, "            if candidate == root or candidate.startswith(root + os.sep):\n",
     "            if candidate.startswith(root):\n"),
    ("M5159", "Glorfindel no longer imports the guard first: a script that imports it alone computes its "
              "paths with nothing installed (HY2b)", "glorfindel/__init__.py",
     "import eregion_core  # noqa: F401 — HY2b: the guard of the operator's ~/.glorfindel, first "
     "(eregion_core/store_guard.py)\n", ""),
]
TESTS = {
    "M5150": AGENT,
    "M5151": AGENT,
    "M5152": WORKTREE,
    "M5153": OPERATOR,
    "M5154": WRITE,
    "M5155": WRITE,
    "M5156": PLACED,
    "M5157": WORKTREE,
    "M5158": PLACED,
    "M5159": T + "test_every_writer_of_glorfindel_s_state_imports_the_guard_first",
}
