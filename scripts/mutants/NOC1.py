"""NOC1 (#1251): the night's guard — what a pull request the night fixed may not merge without Jonathan
(scripts/night_guard.py; docs/sessions.md, « La nuit »). M8018–M8029.
"""
GUARD = "scripts/night_guard.py"
_T = "tests/unit/test_night_guard.py"

MUTANTS = [
    ("M8018", "a protected directory matched by its exact name only: a workflow, a lock, the skill merged at "
              "night (NOC1)", GUARD,
     "        return path.startswith(pattern)\n",
     "        return path == pattern\n"),
    ("M8019", "a test removed or renamed read the other way round: only a test added is said (NOC1)", GUARD,
     "    for name in sorted(before - after):\n",
     "    for name in sorted(after - before):\n"),
    ("M8020", "an xfail no longer recognised: a red test marked expected to fail merges at night (NOC1)", GUARD,
     'SKIP = re.compile(r"\\b(?:pytest\\.|mark\\.)(?:skip|skipif|xfail)\\b',
     'SKIP = re.compile(r"\\b(?:pytest\\.|mark\\.)(?:skip|skipif)\\b'),
    ("M8021", "a skip added beside one already there let through: only a file's first skip is said (NOC1)",
     GUARD,
     "        if news > olds:\n",
     "        if news > olds and olds == 0:\n"),
    ("M8022", "a mutant removed from a lot's file never said (NOC1)", GUARD,
     "    for mid in sorted(set(before) - set(after)):\n",
     "    for mid in sorted(set(after) - set(before)):\n"),
    ("M8023", "a mutant's new text changed without its old one let through: the bug re-introduced is no "
              "longer the one measured (NOC1)", GUARD,
     "        if new0 != new1 and old0 == old1:\n",
     "        if new0 != new1 and old0 != old1:\n"),
    ("M8024", "a lot's file that cannot be read taken for empty: its mutants removed unseen (NOC1)", GUARD,
     '                out.append(f"{path}: its mutants unreadable {side} the change ({e})")\n',
     "                continue\n"),
    ("M8025", "pyproject.toml's dependencies changed at night without Jonathan (NOC1)", GUARD,
     'PYPROJECT = (("project", "dependencies"), ("project", "optional-dependencies"), ("build-system",),',
     'PYPROJECT = (("project", "optional-dependencies"), ("build-system",),'),
    ("M8026", "only a threshold lowered refused: a ceiling raised — the loosening — merges at night (NOC1)",
     GUARD,
     "                elif new[at] != old[at]:\n",
     "                elif new[at] < old[at]:\n"),
    ("M8027", "a named threshold removed never said: a cap taken out of CAPS merges at night (NOC1)", GUARD,
     "            for at in sorted(old):\n",
     "            for at in sorted(set(old) & set(new)):\n"),
    ("M8028", "the change read against main's head, not the merge base: what main did since is taken for the "
              "branch's, and the guard refuses a branch for main's own gestures (NOC1)", GUARD,
     '    since = _git(repo, "merge-base", base, head).strip()\n',
     '    since = _git(repo, "rev-parse", base).strip()\n'),
    ("M8029", "the guard's output not neutralised: a path can carry a review's key into the refusal's comment, "
              "which review_verdict.py check reads (NOC1)", GUARD,
     '    return text.replace("<!--", "&lt;!--")\n',
     "    return text\n"),
]

TESTS = {mid: _T for mid in (f"M{n}" for n in range(8018, 8030))}
