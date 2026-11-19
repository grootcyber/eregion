"""FRS1b (#921): the captures of Dagorlad rendered again — and the renderer that fails at once,
says why, and leaves nothing behind. The 18/11 run: a Chromium found in Playwright's cache but
without its system libraries exited at once; the script raised before its cleanup, and the console
it had started, orphaned, held the caller's output open — a command that seemed to hang. Each
mutant brings back a piece of that: the Chromium not tried before anything starts (M6376), the
console not ended when the render fails (M6377), the console's output on the caller's (M6378),
Chromium's own words dropped from its failure (M6379), the console outliving the script that
started it (M6380). M6376–M6380, measured by tests/unit/test_console_shots.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
SHOTS = "scripts/console_shots.py"

_T = "tests/unit/test_console_shots.py::"

MUTANTS = [
    ("M6376", "a Chromium that cannot run (its libraries missing) is not tried first: the console starts, "
              "then Chromium fails (FRS1b, the defect back)", SHOTS,
     '    broken = chromium_refusal(chromium) if chromium else ""\n',
     '    broken = ""\n'),
    ("M6377", "the console left running when the render fails — Chromium that does not start, a page "
              "that never shows (FRS1b, the defect back)", SHOTS,
     "            stop(server)\n",
     "            pass\n"),
    ("M6378", "the console's output is the caller's: an orphaned console holds the caller's pipe open, "
              "and its refusal is not said by the script (FRS1b, the defect back)", SHOTS,
     '"--parent", str(os.getpid())], cwd=str(work / "cwd"), env=env,\n'
     "                                stdin=subprocess.DEVNULL, stdout=log, stderr=log)\n",
     '"--parent", str(os.getpid())], cwd=str(work / "cwd"), env=env)\n'),
    ("M6379", "Chromium that does not start is said without its own words: « missing libraries? » "
              "instead of the library it lacks (FRS1b)", SHOTS,
     '            raise SystemExit(f"console_shots: Chromium did not start ({why}): {tail(log_path)}")\n',
     '            raise SystemExit(f"console_shots: Chromium did not start ({why})")\n'),
    ("M6380", "the console outlives the script that started it, killed by a signal it cannot catch "
              "(FRS1b)", SHOTS,
     "        while os.getppid() == parent:\n",
     "        while True:\n"),
]
TESTS = {
    "M6376": _T + "test_a_chromium_that_does_not_run_is_said_and_nothing_starts",
    "M6377": _T + "test_the_console_and_chromium_end_when_the_render_fails",
    "M6378": _T + "test_the_consoles_refusal_is_said_at_once_never_on_the_callers_output",
    "M6379": _T + "test_chromium_that_does_not_start_is_said_in_its_own_words_and_ended",
    "M6380": _T + "test_the_console_ends_when_the_script_that_started_it_is_gone",
}
