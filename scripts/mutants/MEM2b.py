"""MEM2b (#1161): the precedent carries the human verdict, the rank prefers a judged one within its keys,
and the memory by keys that does not open falls back on the distance, said loud (glorfindel/memory_keys.py,
glorfindel/memory.py, glorfindel/watch/startup.py, scripts/harness_precedents.py). M7433–M7442."""
_K = "glorfindel/memory_keys.py"
_M = "glorfindel/memory.py"
_S = "glorfindel/watch/startup.py"
_H = "scripts/harness_precedents.py"
_T = "tests/unit/test_memory_verdicts.py"
_TH = "tests/unit/test_harness_precedents.py"
_PREFERRED = '    return keys[:3] + (not c.get("judged"),) + keys[3:]\n'

MUTANTS = [
    ("M7433", "the verdict read and never said: the model sees the action only (MEM2b)", _K,
     '            said = UNREAD if verdicts is None else verdict_said(verdict, meta.get("action"))\n',
     '            said = UNJUDGED\n'),
    ("M7434", "an unjudged precedent says nothing of its verdict (MEM2b)", _K,
     'UNJUDGED = "verdict humain : non jugé"\n', 'UNJUDGED = ""\n'),
    ("M7435", "the verdict out of the rank: the newest first, judged or not (MEM2b)", _K,
     _PREFERRED, '    return keys\n'),
    ("M7436", "the verdict before the keys: a judged cycle of another technique first (MEM2b)", _K,
     _PREFERRED, '    return (not c.get("judged"),) + keys\n'),
    ("M7437", "« unsure » preferred as a verdict, though it says nothing of the threat (MEM2b)", _K,
     'JUDGED = ("right", "wrong")\n', 'JUDGED = ("right", "wrong", "unsure")\n'),
    ("M7438", "the reading of a verdict turned over: a containment judged right said a false alarm (MEM2b)", _K,
     '    acted = (verdict.get("action") or _text(action)) in RESPONSES\n',
     '    acted = (verdict.get("action") or _text(action)) not in RESPONSES\n'),
    ("M7439", "the memory by keys that does not open makes the watch fall: no fallback (MEM2b)", _M,
     "            if not fallback:\n                raise\n", "            raise\n"),
    ("M7440", "the fallback in silence: no card, nobody knows the keys are not on (MEM2b)", _S,
     "        memory_keys.fallback_card(why)\n        return\n", "        return\n"),
    ("M7441", "an import into a file that is no SQLite database raises, never refused (MEM2b)", _K,
     "    except sqlite3.DatabaseError as exc:\n", "    except sqlite3.NotSupportedError as exc:\n"),
    ("M7442", "the harness's verdicts never reach the keys: passage 1 replayed without them (MEM2b)", _H,
     '        judged = {"verdicts": lambda: verdicts_of(case, index)} if mode == KEYS else {}\n',
     '        judged = {"verdicts": lambda: {}} if mode == KEYS else {}\n'),
]
TESTS = {
    "M7433": f"{_T}::test_a_judged_precedent_says_its_verdict_and_its_day",
    "M7434": f"{_T}::test_an_unjudged_precedent_says_it_is_not_judged",
    "M7435": f"{_T}::test_a_judged_precedent_comes_before_a_newer_unjudged_one_of_the_same_keys",
    "M7436": f"{_T}::test_a_verdict_never_wins_over_the_keys",
    "M7437": f"{_T}::test_unsure_is_said_and_never_preferred",
    "M7438": f"{_T}::test_a_judged_precedent_says_its_verdict_and_its_day",
    "M7439": f"{_T}::test_the_keys_that_do_not_open_fall_back_on_the_distance_said_loud",
    "M7440": f"{_T}::test_the_keys_that_do_not_open_fall_back_on_the_distance_said_loud",
    "M7441": f"{_T}::test_an_import_into_a_file_that_is_no_sqlite_database_is_refused",
    "M7442": f"{_TH}::test_the_keys_precedents_say_their_verdict_and_the_distances_none",
}
