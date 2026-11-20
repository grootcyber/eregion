"""G1d (Partie de #76): a fault waits for the previous exercise window on its target, its grace
included — the run and the preflight refuse before the contract and the cloud, and say until when;
what cannot be read is never « no window ». M6865–M6874 and M6893–M6896 (the review), measured by
tests/unit/test_gothmog.py."""
WIN = "gothmog/runner/windows.py"
EN = "gothmog/runner/engine.py"
_T = "tests/unit/test_gothmog.py"
_UNREADABLE = f"{_T}::test_a_window_that_cannot_be_read_refuses"

MUTANTS = [
    ("M6865", "the windows' place, a file and no directory, taken for no window at all (G1d)", WIN,
     "    if not stat.S_ISDIR(st.st_mode):\n"
     "        return \"window: the exercise windows' place is no directory — not run\"\n",
     "    if not stat.S_ISDIR(st.st_mode):\n"
     "        return \"\"\n"),
    ("M6866", "a window that cannot be read skipped: an unreadable file read as « free » (G1d)", WIN,
     '            return f"window: {path.name} cannot be read ({type(e).__name__}) — not run"\n',
     "            continue\n"),
    ("M6867", "a file that holds no window skipped (G1d)", WIN,
     '            return f"window: {path.name} holds no window — not run"\n',
     "            continue\n"),
    ("M6868", "a tombstone read as a window: a fault refused by a window long gone (G1d)", WIN,
     "        if window.get(\"purged_at\"):\n"
     "            continue                                 # a tombstone: no window left\n",
     ""),
    ("M6869", "a window with no start, expiry or targets skipped (G1d)", WIN,
     '            return f"window: {path.name} has no readable start, expiry or targets — not run"\n',
     "            continue\n"),
    ("M6870", "the target compared with its case: the same VM, written otherwise, free (G1d)", WIN,
     '    text = str(target).lower().rstrip("/")\n',
     '    text = str(target).rstrip("/")\n'),
    ("M6871", "a closed window never holds the next fault: the grace forgotten, the 20/11 chain "
     "again (G1d)", WIN,
     '        if keys & set().union(*(_keys(t) for t in aimed)) and last > now:\n',
     '        if keys & set().union(*(_keys(t) for t in aimed)) and last > now and window.get("end") is None:\n'),
    ("M6872", "the run never reads the windows: a fault started inside the previous one's (G1d)", EN,
     "        busy = self._window_busy(fault)\n"
     "        if busy:\n"
     "            console.print(f\"[red]Refused:[/red] {escape(busy)}\")\n"
     "            return RunOutcome(run_id, \"REFUSED\", error=busy)\n"
     "        console.rule(",
     "        console.rule("),
    ("M6873", "the preflight never reads the windows: « could run », then refused at the run (G1d)", EN,
     "        busy = self._window_busy(fault)   # G1d: a local read, before the watch and the contract\n"
     "        if busy:\n",
     "        busy = \"\"\n"
     "        if busy:\n"),
    ("M6874", "the run's window closed on the wall clock, not the engine's: what the next run "
     "reads is not what this one kept (G1d)", EN,
     '            close_window(run_id, injector="gothmog", now=self._now())\n',
     '            close_window(run_id, injector="gothmog")\n'),
    ("M6893", "a window that does not say its injector skipped: read as free (G1d, review 4)", WIN,
     '        if window.get("injector") not in (None, "gothmog"):\n',
     '        if window.get("injector") != "gothmog":\n'),
    ("M6894", "the run reads the watch before the windows: V1 first, the channel read before the "
     "local refusal (G1d, review 3)", EN,
     '        busy = self._window_busy(fault)\n        if busy:\n            console.print(f"[red]Refused:[/red] {escape(busy)}")\n            return RunOutcome(run_id, "REFUSED", error=busy)\n        console.rule(f"[bold red]Gothmog — {fault[\'name\']}[/bold red]")\n        console.print(f"  Engine  : {fault[\'engine\']} / {fault[\'engine_ref\']}")\n        console.print(f"  Targets : {\', \'.join(fault[\'targets\'][\'names\'])}\\n")\n        # 0. A live Glorfindel watch, before anything reaches the cloud (V1).\n        refused = self._no_watch(run_id, without_glorfindel)\n        if refused:\n            return refused\n',
     '        console.rule(f"[bold red]Gothmog — {fault[\'name\']}[/bold red]")\n        console.print(f"  Engine  : {fault[\'engine\']} / {fault[\'engine_ref\']}")\n        console.print(f"  Targets : {\', \'.join(fault[\'targets\'][\'names\'])}\\n")\n        # 0. A live Glorfindel watch, before anything reaches the cloud (V1).\n        refused = self._no_watch(run_id, without_glorfindel)\n        if refused:\n            return refused\n        busy = self._window_busy(fault)\n        if busy:\n            console.print(f"[red]Refused:[/red] {escape(busy)}")\n            return RunOutcome(run_id, "REFUSED", error=busy)\n'),
    ("M6895", "every window file read, however many: past the bound, some never read (G1d, "
     "review 5)", WIN,
     '    if len(paths) > MAX_WINDOW_FILES:\n        return f"window: more than {MAX_WINDOW_FILES} exercise windows, not all read — not run"\n',
     ""),
    ("M6896", "windows that cannot be listed read as none (G1d, review 5)", WIN,
     '        return f"window: the exercise windows cannot be listed ({type(e).__name__}) — not run"\n',
     '        return ""\n'),
]

TESTS = {
    "M6865": _UNREADABLE,
    "M6866": _UNREADABLE,
    "M6867": _UNREADABLE,
    "M6868": f"{_T}::test_past_its_grace_or_on_another_vm_a_window_holds_nothing",
    "M6869": _UNREADABLE,
    "M6870": f"{_T}::test_the_target_is_compared_without_its_case",
    "M6871": f"{_T}::test_a_fault_waits_for_the_previous_window_on_its_target_and_says_until_when",
    "M6872": f"{_T}::test_a_fault_waits_for_the_previous_window_on_its_target_and_says_until_when",
    "M6873": f"{_T}::test_a_fault_waits_for_the_previous_window_on_its_target_and_says_until_when",
    "M6874": f"{_T}::test_a_run_s_own_window_holds_the_next_one_until_its_grace_ends",
    "M6893": f"{_T}::test_a_technique_s_window_does_not_hold_a_fault",
    "M6894": f"{_T}::test_the_window_is_read_before_the_watch_and_the_contract",
    "M6895": f"{_T}::test_more_windows_than_the_bound_are_not_all_read_and_refuse",
    "M6896": f"{_T}::test_windows_that_cannot_be_listed_refuse",
}
