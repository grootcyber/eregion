"""NOC1 (#1251): the night's guard — what a pull request the night fixed may not merge without Jonathan
(scripts/night_guard.py; docs/sessions.md, « La nuit »). M8018–M8029, then M8032–M8045 after the
review's first round (the collection, the aliases, the reasons, the loader's child).
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
     'SKIP_WORDS = {"skip": "skip", "skipif": "skipif", "xfail": "xfail",',
     'SKIP_WORDS = {"skip": "skip", "skipif": "skipif",'),
    ("M8021", "a skip read by its kind alone, not by the test it sits in: a skip moved from a test to a red one "
              "merges at night (NOC1, the review's 8th finding)", GUARD,
     '        for scope, kind in sorted(skipped["after"] - skipped["before"]):\n',
     '        for scope, kind in sorted(s for s in skipped["after"] - skipped["before"]\n'
     '                                  if s[1] not in {k for _, k in skipped["before"]}):\n'),
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

MUTANTS += [
    ("M8032", "a collected file must match both of pytest's patterns: no file is, no test is ever counted (NOC1)",
     GUARD,
     "    return fnmatch.fnmatchcase(name, COLLECTED[0]) or fnmatch.fnmatchcase(name, COLLECTED[1])\n",
     "    return fnmatch.fnmatchcase(name, COLLECTED[0]) and fnmatch.fnmatchcase(name, COLLECTED[1])\n"),
    ("M8033", "an importorskip no longer recognised: a test skipped for want of a module merges at night (NOC1)",
     GUARD,
     ' "importorskip": "importorskip",\n',
     "\n"),
    ("M8034", "the loader's timeout dropped: a lot's file that never ends holds the night (NOC1)", GUARD,
     '                       timeout=timeout, env={"PATH": CHILD_PATH, "HOME": tmp}, preexec_fn=_limits(timeout))\n',
     '                       env={"PATH": CHILD_PATH, "HOME": tmp}, preexec_fn=_limits(timeout))\n'),
    ("M8035", "the child no longer isolated (-I): the user's site and the environment's PYTHON* reach it (NOC1)",
     GUARD,
     '            done = run([sys.executable, "-I", "-c", _LOADER, str(path)]',
     '            done = run([sys.executable, "-c", _LOADER, str(path)]'),
    ("M8036", "the child inherits the session's environment (GH_CONFIG_DIR, GIT_CONFIG_GLOBAL, the HOME) (NOC1)",
     GUARD,
     '                       timeout=timeout, env={"PATH": CHILD_PATH, "HOME": tmp}, preexec_fn=_limits(timeout))\n',
     '                       timeout=timeout, env=None, preexec_fn=_limits(timeout))\n'),
    ("M8037", "a lot's file run without its syntax tree checked: an import, an open, an eval run (NOC1)", GUARD,
     "    precheck(tree)\n    with tempfile.TemporaryDirectory",
     "    with tempfile.TemporaryDirectory"),
    ("M8038", "getattr let through the syntax check: any attribute reached by its name (NOC1)", GUARD,
     'FORBIDDEN = {"open", "eval", "exec", "compile", "getattr", ',
     'FORBIDDEN = {"open", "eval", "exec", "compile", '),
    ("M8039", "a reason added to a mutant never said: EQUIVALENT takes a survivor out of the count at night (NOC1)",
     GUARD,
     "        if why1 and why1 != why0:\n",
     "        if False:\n"),
    ("M8040", "a mutant's file changed never said: it aims elsewhere, where its old text also is (NOC1)", GUARD,
     "        if file0 != file1:\n",
     "        if False:\n"),
    ("M8041", "`import pytest as pt` not followed: pt.skip(...) merges at night (NOC1)", GUARD,
     "                if a.asname:\n                    names[a.asname] = a.name\n",
     "                if a.asname:\n                    pass\n"),
    ("M8042", "`from pytest import skip` not followed: skip(...) merges at night (NOC1)", GUARD,
     '                    names[a.asname or a.name] = f"{node.module}.{a.name}"\n',
     "                    pass\n"),
    ("M8043", "unittest's self.skipTest(...) not recognised (NOC1)", GUARD,
     '        if isinstance(node, ast.Attribute) and node.attr == "skipTest":\n',
     "        if False:\n"),
    ("M8044", "a conftest.py no longer protected: collect_ignore_glob in it takes every test out (NOC1)", GUARD,
     '    ("conftest.py", "touches a conftest.py: what pytest collects, skips or deselects"),\n',
     ""),
    ("M8045", "the tests counted in any module under tests/, collected or not: a test moved to helpers_x.py, "
              "out of the run, passes (NOC1)", GUARD,
     "                if _collected(path):\n                    names = named_tests",
     "                if _scanned(path):\n                    names = named_tests"),
]

TESTS = {mid: _T for mid in [f"M{n}" for n in range(8018, 8030)] + [f"M{n}" for n in range(8032, 8046)]}
