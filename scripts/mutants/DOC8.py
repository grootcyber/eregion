"""DOC8 (#1155): a changelog fragment says "Tests:", the French spacing before the colon refused. M7410, M7411."""
MUTANTS = [
    ("M7410", "scripts/release.py accepts a fragment's « - Tests : » again: the refusal of FRENCH_TESTS removed (DOC8)",
     "scripts/release.py",
     '            if FRENCH_TESTS.match(line):\n'
     '                raise ValueError(f"ligne {i} : « Tests : » — en anglais, « Tests: », sans espace avant les deux-points")\n',
     ""),
    ("M7411", "scripts/release.py lets a no-break space before the colon through: left out of FRENCH_TESTS (DOC8)",
     "scripts/release.py", 'FRENCH_TESTS = re.compile(r"\\s*[-*]\\s+Tests[ \\u00a0\\u202f]+:")\n',
     'FRENCH_TESTS = re.compile(r"\\s*[-*]\\s+Tests[ \\u202f]+:")\n'),
]
TESTS = {"M7410": "tests/unit/test_release.py::test_a_malformed_fragment_is_refused_and_nothing_is_written",
         "M7411": "tests/unit/test_release.py::test_a_malformed_fragment_is_refused_and_nothing_is_written"}
