"""HY2b (#791): a probe of an agent session, outside the suite, never writes in the operator's real
~/.glorfindel — refused and said before it happens, by an audit hook eregion_core installs in an agent
session only (eregion_core/store_guard.py). M5150–M5159, measured by tests/unit/test_store_guard.py:
probes in fresh interpreters over an operator simulated in tmp (its system home a folder of tmp_path),
never this workstation's. M5190–M5194, the review's round 1: the memory of cycles (ChromaDB, written
from Rust) refused before it is opened, a worktree's code guarded wherever it runs, the way out said.
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
    # M5159 is caught by a reading of the code only (test_every_writer_…: the first import of
    # glorfindel/__init__.py), a belt: the probes still meet the guard without it, through the first
    # import of glorfindel/agent.py (eregion_core.models), before any path of the store is written.
    ("M5159", "Glorfindel no longer imports the guard first: a script that imports it alone computes its "
              "paths with nothing installed (HY2b; caught by a reading of the code only, a belt)",
     "glorfindel/__init__.py",
     "import eregion_core  # noqa: F401 — HY2b: the guard of the operator's ~/.glorfindel, first "
     "(eregion_core/store_guard.py)\n", ""),
]
MEMORY = "glorfindel/memory.py"
CODE = T + "test_a_probe_that_runs_a_lot_s_worktree_code_from_elsewhere_is_refused_and_said"
CYCLES = T + "test_the_memory_of_cycles_is_refused_before_chromadb_opens_it"
MUTANTS += [
    ("M5190", "the memory of cycles no longer checked: an agent session's CycleMemory opens ChromaDB in the "
              "operator's ~/.glorfindel/cycles, its store written from Rust, unseen (HY2b, review round 1)",
     MEMORY, "        store_guard.check(storage_path)\n", ""),
    ("M5191", "the memory checked once ChromaDB has opened it: its sqlite and its index already written in "
              "the operator's ~/.glorfindel/cycles when the refusal comes (HY2b, review round 1)", MEMORY,
     "        store_guard.check(storage_path)\n        storage_path.mkdir(parents=True, exist_ok=True)\n"
     "        self._client = chromadb.PersistentClient(path=str(storage_path))\n",
     "        storage_path.mkdir(parents=True, exist_ok=True)\n"
     "        self._client = chromadb.PersistentClient(path=str(storage_path))\n"
     "        store_guard.check(storage_path)\n"),
    ("M5192", "the checkout the code runs from no longer looked at: a probe run from elsewhere on a lot's "
              "worktree code writes in the operator's ~/.glorfindel (HY2b, review round 1)", GUARD,
     "    if _in_worktree(Path(__file__) if here is None else here):\n", "    if False:\n"),
    ("M5193", "a refused opening of the memory no longer said: `glorfindel report` swallows the error, the "
              "probe never knows why (HY2b, review round 1)", GUARD,
     '    said = message(found[0], _installed["why"], found[1])\n    _say(said)\n',
     '    said = message(found[0], _installed["why"], found[1])\n'),
    # HY2c (#800) said this way out to the operator alone, never to a probe (OPERATOR_ONLY): the mutant
    # is the same, said by the line HY2c wrote.
    ("M5194", "the way out of a worktree no longer said: an operator refused for his current folder is not "
              "told to run elsewhere (HY2b, review round 1; HY2c)", GUARD,
     '    operator = OPERATOR_ONLY if why == WORKTREE_CWD else ""\n',
     '    operator = ""\n'),
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
    "M5190": CYCLES,
    "M5191": CYCLES,
    "M5192": CODE,
    "M5193": CYCLES,
    "M5194": WORKTREE,
}
