"""SEC-K (#847): .github/CODEOWNERS names the files that a workflow holding a credential runs, and
nothing else; tests/unit/test_codeowners.py derives them from the workflows. M5741–M5751: the list
itself (a path dropped, the catch-all back), the job that signs running a script every lot changes,
and each way the test sees a file — so that it never passes by seeing nothing.
"""
OWNERS = ".github/CODEOWNERS"
GUARD = "tests/unit/test_codeowners.py"
IMAGE_CHECK = "scripts/image_check.py"
T = "tests/unit/test_codeowners.py::"

MUTANTS = [
    ("M5741", "a script run with the signing token owned by no line: a session changes it unseen (SEC-K)",
     OWNERS, "/scripts/retry.sh                       @grootcyber\n", ""),
    ("M5742", "the catch-all back: every pull request waits for the maintainer once his rule is on (SEC-K)",
     OWNERS, "/.github/                               @grootcyber\n",
     "*                                       @grootcyber\n/.github/                               @grootcyber\n"),
    ("M5743", "the job that signs imports component_check.py again, which most lots change (SEC-K)",
     IMAGE_CHECK,
     'GLORFINDEL_ONLY_DEPS = ("langgraph", "chromadb", "anthropic", "discord", "fastapi", "uvicorn",\n'
     '                        "azure.mgmt.recoveryservicesbackup")\n',
     'sys.path.insert(0, str(REPO / "scripts"))\n'
     'from component_check import GLORFINDEL_ONLY_DEPS  # noqa: E402\n'),
    ("M5744", "a job's secrets never seen: the workshop's Discord jobs taken as holding nothing (SEC-K)",
     GUARD, "    if SECRET.search(text):\n", "    if False:\n"),
    ("M5745", "a job's write permissions never seen: `id-token: write` alone holds nothing (SEC-K)",
     GUARD, '        return any(value == "write" for value in perms.values())\n', "        return False\n"),
    ("M5746", "a sparse checkout never read: what it puts on the runner runs unowned (SEC-K)",
     GUARD, "    for paths in _sparse(job):\n", "    for paths in []:\n"),
    ("M5747", "what a script imports or calls next to it never followed (SEC-K)",
     GUARD, "            todo.extend(sorted(follows(root, rel) - seen))\n", "            pass\n"),
    ("M5748", "the CD of Imladris never read: what it installs left out of the list (SEC-K)",
     GUARD, "    files = closure(root, cd_files(root)) if (root / CD).is_file() else set()\n",
     "    files = set()\n"),
    ("M5749", "a file named after the standard library next to a script never seen (SEC-K)",
     GUARD, "        if regular and name in sys.stdlib_module_names:\n", "        if False:\n"),
    ("M5750", "a job that checks nothing out: the text of its run taken as files it runs (SEC-K)",
     GUARD, "    if not _checks_out(job):\n        return files\n", ""),
    ("M5751", "a line taken to cover a path it only begins: /script/ for scripts/ (SEC-K)",
     GUARD, '    return pattern == f"/{rel}" or (pattern.endswith("/") and f"/{rel}/".startswith(pattern))\n',
     '    return f"/{rel}".startswith(pattern.rstrip("/"))\n'),
]
TESTS = {
    "M5741": T + "test_every_file_a_credentialed_job_runs_is_owned",
    "M5742": T + "test_the_codeowners_is_plain_and_has_no_catch_all",
    "M5743": T + "test_every_file_a_credentialed_job_runs_is_owned",
    "M5744": T + "test_a_job_holds_a_credential_by_a_secret_or_a_write",
    "M5745": T + "test_a_job_holds_a_credential_by_a_secret_or_a_write",
    "M5746": T + "test_a_sparse_checkout_gives_its_code_never_its_data",
    "M5747": T + "test_what_a_credentialed_job_runs_and_what_it_only_reads",
    "M5748": T + "test_every_line_owns_a_file_a_credentialed_job_runs",
    "M5749": T + "test_a_file_named_after_the_standard_library_next_to_a_script_is_found",
    "M5750": T + "test_a_job_that_checks_nothing_out_runs_nothing_of_the_repository",
    "M5751": T + "test_a_line_covers_its_file_or_what_its_directory_holds",
}
