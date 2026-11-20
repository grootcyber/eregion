"""DEP4 (#990): the weekly issues say what a human accepted (requirements/audit-accepted.json), and an
accepted advisory turns the run red no more. M6812–M6814; the review, M6851–M6854."""
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
    ("M6851", "a reason's « < » written as is: a key of an issue carried into the body (DEP4, review)", _S,
     '.replace("<", "&lt;")', ""),
    ("M6852", "an acceptance withdrawn leaves the run green (DEP4, review)", _S,
     '        done.append(f"#{issue.number} : acceptation retirée")\n        new = True\n',
     '        done.append(f"#{issue.number} : acceptation retirée")\n'),
    ("M6853", "an accepted advisory found back turns the run red (DEP4, review)", _S,
     '(CI2).")\n        new = not ok\n', '(CI2).")\n        new = True\n'),
    ("M6854", "an acceptance dated in the future is taken (DEP4, review)", _S,
     "return date.fromisoformat(since) <= datetime.now(timezone.utc).date()",
     "return bool(date.fromisoformat(since))"),
]
TESTS = {
    "M6812": f"{_T}::test_an_open_issue_accepted_since_says_it_without_a_comment",
    "M6813": f"{_T}::test_an_accepted_advisory_opens_its_issue_saying_so_and_the_run_stays_green",
    "M6814": f"{_T}::test_an_accepted_advisory_opens_its_issue_saying_so_and_the_run_stays_green",
    "M6851": f"{_T}::test_a_reason_carrying_a_key_never_lends_its_issue_to_another_advisory",
    "M6852": f"{_T}::test_an_acceptance_withdrawn_turns_the_run_red_once",
    "M6853": f"{_T}::test_an_accepted_advisory_found_back_stays_green",
    "M6854": f"{_T}::test_an_acceptance_of_no_real_date_or_too_long_refuses_the_list",
}
