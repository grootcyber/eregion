"""DEP4 (#990): the weekly issues say what a human accepted (requirements/audit-accepted.json), and an
accepted advisory turns the run red no more. M6812–M6814."""
_S = "scripts/pip_audit_issues.py"
_T = "tests/unit/test_pip_audit_issues.py"

MUTANTS = [
    ("M6812", "an accepted advisory's issue no longer says it was accepted (DEP4)", _S,
     "        + _accepted_said(ok) +\n", "        +\n"),
    ("M6813", "opening the issue of an accepted advisory turns the run red again (DEP4)", _S,
     '        done.append(f"ouverte : {title(adv)} {url}" + (" (acceptée)" if ok else ""))\n        return not ok\n',
     '        done.append(f"ouverte : {title(adv)} {url}" + (" (acceptée)" if ok else ""))\n        return True\n'),
    ("M6814", "the weekly run no longer reads the repository's list of accepted advisories (DEP4)", _S,
     'path = args.accepted or (DEFAULT_ACCEPTED if args.mode == "issues"',
     'path = args.accepted or ("" if args.mode == "issues"'),
]
TESTS = {
    "M6812": f"{_T}::test_an_open_issue_accepted_since_says_it_without_a_comment",
    "M6813": f"{_T}::test_an_accepted_advisory_opens_its_issue_saying_so_and_the_run_stays_green",
    "M6814": f"{_T}::test_an_accepted_advisory_opens_its_issue_saying_so_and_the_run_stays_green",
}
