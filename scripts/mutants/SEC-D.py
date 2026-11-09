"""SEC-D (#636, P-03): SECURITY.md's supported line follows a minor release. `make release` (prepare)
rewrites its table when the minor changes — the supported line becomes X.Y.x, the « older » line names
the one it replaces —, commits it with the version, and shows it in a dry run; a patch leaves it.
M4560: prepare no longer rewrites SECURITY.md (a minor's version PR goes red on test_readme.py);
M4561: a patch rewrites it too; M4562: rewritten but never committed (the tree left dirty)."""
RELEASE = "scripts/release.py"
_REL = "tests/unit/test_release.py::"

MUTANTS = [
    ("M4560", "prepare no longer rewrites SECURITY.md: a minor release keeps the old supported line "
              "(SEC-D, the defect back)", RELEASE,
     "    if edits and followed != security:\n",
     "    if False:\n"),
    ("M4561", "a patch release rewrites SECURITY.md too: the « older » line names the supported line "
              "itself (SEC-D)", RELEASE,
     "    if new is None or len(found) != 1 or (int(found[0][0]), int(found[0][1])) == new[:2]:\n",
     "    if new is None or len(found) != 1:\n"),
    ("M4562", "SECURITY.md rewritten but left out of the version's commit: the tree dirty, the PR without "
              "it (SEC-D)", RELEASE,
     '    staged += ["SECURITY.md"] if "SECURITY.md" in edits else []\n',
     "    staged += []\n"),
]
TESTS = {
    "M4560": f"{_REL}test_a_minor_release_moves_security_md_to_its_line_in_the_same_commit",
    "M4561": f"{_REL}test_a_patch_release_leaves_security_md_as_it_is",
    "M4562": f"{_REL}test_a_minor_release_moves_security_md_to_its_line_in_the_same_commit",
}
