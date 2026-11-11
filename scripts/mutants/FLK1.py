"""FLK1 (#723): ChromaDB's embedding model fetched by one process at a time — the suite wraps
ChromaDB's own check-then-fetch in a file lock, lazily (M4790, the defect back; M4792; M4811 when
ChromaDB is imported after the fixture), the lock taken between processes (M4791) and by the
harness too (M4812); a lock that cannot be taken, or a ChromaDB without the method, is said, never
an error of its own (M4793, M4810). The guard of Imladris's name reads `git ls-files -z`: a name
that is not ASCII is read, never skipped (M4794). M4790–M4794, then M4810–M4812 (review 1); the lock re-entrant in a process (M4813).

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
CONFTEST = "tests/unit/conftest.py"
SCRIPT = "scripts/chroma_model.py"
GUARD = "scripts/host_name.py"
HARNESS = "scripts/mutation_check.py"
T = "tests/unit/test_chroma_model.py::"

MUTANTS = [
    ("M4790", "the suite's lock never installed: the workers, at once, fetch the model into one place again "
              "(FLK1, the defect back)", CONFTEST,
     "    return script.lock_downloads(say=lambda text: warnings.warn(pytest.PytestWarning(text)))\n",
     "    return None\n"),
    ("M4791", "the lock never taken between processes: one fetches the model beside the one that fetches "
              "it (FLK1)", SCRIPT,
     "        fcntl.flock(lock, fcntl.LOCK_EX)\n",
     ""),
    ("M4792", "ChromaDB's check-then-fetch wrapped, but not in the lock (FLK1)", SCRIPT,
     "        with held(Path(self.DOWNLOAD_PATH).parent, say=say):\n"
     "            return original(self, *args, **kwargs)\n",
     "        return original(self, *args, **kwargs)\n"),
    ("M4793", "a cache that is not writable (root's, from the old image) puts every test of the session "
              "in error, the model there or not (FLK1, review 1)", SCRIPT,
     "    except OSError as exc:         # said, never a verdict\n",
     "    except ImportError as exc:     # said, never a verdict\n"),
    ("M4794", "the guard reads `git ls-files` without -z: a name that is not ASCII is quoted, then "
              "skipped unsaid (FLK1)", GUARD,
     ('["git", "ls-files", "-z"]', 'names = out.split("\\0")'),
     ('["git", "ls-files"]', 'names = out.split("\\n")')),
    ("M4810", "a ChromaDB without the method fetches unlocked, unsaid: the race back with an upgrade "
              "(FLK1, review 1)", SCRIPT,
     "        say(f\"ChromaDB's model: {CLASS}.{METHOD} is not in",
     "        (lambda *_, **__: None)(f\"ChromaDB's model: {CLASS}.{METHOD} is not in"),
    ("M4811", "ChromaDB imported after the fixture never wrapped: the race back in every worker that "
              "imports it later (FLK1, review 1)", SCRIPT,
     "    sys.meta_path.insert(0, _OnImport(target, lambda m: wrap(m, say)))\n",
     ""),
    ("M4812", "the harness prepares the model outside the lock: a harness and a `pytest -n 4` fetch it "
              "beside each other (FLK1, review 1)", HARNESS,
     "        with _model_lock(say):\n            functions.DefaultEmbeddingFunction()([\"eregion\"])\n",
     "        with contextlib.nullcontext():\n            functions.DefaultEmbeddingFunction()([\"eregion\"])\n"),
]
MUTANTS += [
    ("M4813", "the lock not re-entrant: the harness (or CI8's step) holds it, then ChromaDB, wrapped, waits "
              "on it for ever (FLK1, review 1)", SCRIPT,
     '        if mine["depth"]:\n',
     "        if False:\n"),
]
TESTS = {
    "M4790": f"{T}test_workers_that_embed_at_once_fetch_the_model_once "
             f"{T}test_the_locked_chromadb_has_what_the_suite_wraps_and_this_session_wrapped_it",
    "M4791": f"{T}test_a_second_process_waits_for_the_one_that_holds_the_lock "
             f"{T}test_chromadb_s_check_then_fetch_runs_under_the_lock",
    "M4792": T + "test_chromadb_s_check_then_fetch_runs_under_the_lock",
    "M4793": T + "test_a_cache_that_is_not_writable_is_said_and_chromadb_goes_on_as_before",
    "M4794": "tests/unit/test_host_name.py::test_a_tracked_file_whose_name_is_not_ascii_is_read",
    "M4810": T + "test_a_chromadb_without_the_method_is_said",
    "M4811": T + "test_chromadb_imported_after_the_fixture_is_wrapped_when_it_is",
    "M4812": "tests/unit/test_mutation_shards.py::test_the_harness_prepares_the_model_under_the_suite_s_lock",
    "M4813": T + "test_a_process_that_holds_the_lock_takes_it_again_without_waiting_on_itself",
}
