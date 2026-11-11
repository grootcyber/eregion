"""FLK1 (#723): ChromaDB's embedding model made ready once per test session, under a file lock, by
the conftest — never by each worker at once (M4790, the defect back), never beside a process that
holds the lock (M4791), never fetched again when it is there (M4792); a preparation that fails is
said, never stops the session (M4793). The guard of Imladris's name reads `git ls-files -z`: a name
that is not ASCII is read, never skipped (M4794).

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
CONFTEST = "tests/unit/conftest.py"
SCRIPT = "scripts/chroma_model.py"
GUARD = "scripts/host_name.py"
T = "tests/unit/test_chroma_model.py::"

MUTANTS = [
    ("M4790", "the preparation removed: the workers, at once, fetch the model into one place again (FLK1, "
              "the defect back)", CONFTEST,
     "        outcome = script.prepare_once(say=lambda text: warnings.warn(pytest.PytestWarning(text)))\n",
     "        outcome = None\n"),
    ("M4791", "the lock never taken: a process fetches the model beside the one that prepares it (FLK1)",
     SCRIPT,
     "        fcntl.flock(lock, fcntl.LOCK_EX)\n",
     ""),
    ("M4792", "the model fetched even when it is there: a second process fetches it again, a network "
              "needed each time (FLK1)", SCRIPT,
     "        if ready():\n            return True\n        try:\n",
     "        try:\n"),
    ("M4793", "a preparation that fails stops the session: no network, every test red (FLK1)", SCRIPT,
     "        except Exception as exc:   # said, never a verdict\n",
     "        except ImportError as exc:   # said, never a verdict\n"),
    ("M4794", "the guard reads `git ls-files` without -z: a name that is not ASCII is quoted, then "
              "skipped unsaid (FLK1)", GUARD,
     ('["git", "ls-files", "-z"]', 'names = out.split("\\0")'),
     ('["git", "ls-files"]', 'names = out.split("\\n")')),
]
TESTS = {
    "M4790": T + "test_the_suite_prepares_the_model_once_before_its_tests_with_workers_in_parallel",
    "M4791": T + "test_a_second_process_waits_for_the_first_then_finds_the_model_there",
    "M4792": f"{T}test_a_model_already_there_is_neither_fetched_nor_loaded "
             f"{T}test_a_second_process_waits_for_the_first_then_finds_the_model_there",
    "M4793": T + "test_a_preparation_that_fails_is_said_never_raised",
    "M4794": "tests/unit/test_host_name.py::test_a_tracked_file_whose_name_is_not_ascii_is_read",
}
