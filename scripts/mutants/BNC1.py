"""BNC1 (#682): the bench read by the machine — `make bench-preflight` (the step 0 in one verdict) and
`make bench-report` (a run's chronology, composed alone), read only, no identifier printed.
M4676–M4685, measured by tests/unit/test_bench_preflight.py and tests/unit/test_bench_report.py."""
PRE = "scripts/bench_preflight.py"
REP = "scripts/bench_report.py"
SHARED = "scripts/bench_shared.py"
READER = "scripts/bench_h0_reader.py"
_P = "tests/unit/test_bench_preflight.py"
_R = "tests/unit/test_bench_report.py"

MUTANTS = [
    ("M4676", "an assignment read as covering a scope whose path only begins as its own: H0's role on "
     "`rg-celeb` held for `rg-celebrimbor` (BNC1)", PRE,
     '    return bool(a) and (s == a or s.startswith(a + "/") or a == "/")\n',
     '    return bool(a) and (s.startswith(a) or a == "/")\n'),
    ("M4677", "a role's notActions dropped from its definition: an action it takes back read as held "
     "by H0 or Orodruin (BNC1)", PRE,
     '        out[rid] = list((match[0].get("permissions") if match else None) or [])\n',
     '        out[rid] = [{"actions": p.get("actions") or []}\n'
     '                    for p in (match[0].get("permissions") if match else None) or []]\n'),
    ("M4678", "« Restore Staging » read as in place wherever it is assigned: on the group, the drift "
     "is not said (BNC1)", PRE,
     '    if any(str(a.get("roleDefinitionName") or "") == STAGING_ROLE and str(a.get("scope") or "").rstrip("/").lower() == staging\n',
     '    if any(str(a.get("roleDefinitionName") or "") == STAGING_ROLE\n'),
    ("M4679", "the tenant's restore role from before SEC17, `runCommand/action` still in it, read as "
     "clean (BNC1)", PRE,
     '    elif action_held(list(role.get("permissions") or []), RESTORE_RUN_COMMAND):\n',
     '    elif False:\n'),
    ("M4680", "the age of the oldest recovery point taken for the newest: a recent point read as too "
     "old (BNC1)", PRE,
     '    age_h = (ctx.now.timestamp() - max(times)) / 3600\n',
     '    age_h = (ctx.now.timestamp() - min(times)) / 3600\n'),
    ("M4681", "a warning stops the run: Orodruin deallocated at the step 0 exits 1 (BNC1)", PRE,
     '    return "\\n".join(bs.scrub(x) for x in out), 1 if n[bs.FAIL] else 0\n',
     '    return "\\n".join(bs.scrub(x) for x in out), 1 if n[bs.FAIL] or n[bs.WARN] else 0\n'),
    ("M4682", "an IP address printed as it is: H0's in a line of `glorfindel-host-status` (BNC1)", SHARED,
     '    return IPV4.sub("<ip>", out)\n',
     '    return out\n'),
    ("M4683", "a caller known by its appId alone read as unknown: the console's Run Commands lose their "
     "role, the neutralization is not found (BNC1)", SHARED,
     '        seen = _ids(event.get("caller"), claims.get("appid"), claims.get("azp"), claims.get("oid"),\n',
     '        seen = _ids(event.get("caller"), claims.get("azp"), claims.get("oid"),\n'),
    ("M4684", "a refused Run Command of the console taken for the neutralization: the last one before "
     "the restore, whatever its status (BNC1)", REP,
     '    neutral = [r for r in rcs if r["role"] in ("console", "bot") and r["status"].lower() == "succeeded"\n',
     '    neutral = [r for r in rcs if r["role"] in ("console", "bot")\n'),
    ("M4685", "the H0 reader sends a cycle's whole outcome back: its error, an id in it, leaves H0 (BNC1)",
     READER,
     '            "outcome": {k: o[k] for k in _OUTCOME_KEYS if k in o}}\n',
     '            "outcome": dict(o)}\n'),
]
TESTS = {
    "M4676": f"{_P}::test_h0_s_rights_read_wildcards_and_not_actions",
    "M4677": f"{_P}::test_h0_s_rights_read_wildcards_and_not_actions",
    "M4678": f"{_P}::test_the_staging_role_on_the_group_is_not_the_staging_account_s",
    "M4679": f"{_P}::test_the_0911_bench_is_stopped_before_the_attack",
    "M4680": f"{_P}::test_a_bench_in_order_lets_the_run_go",
    "M4681": f"{_P}::test_orodruin_deallocated_is_a_warning_and_its_contract_is_never_published",
    "M4682": f"{_P}::test_no_identifier_leaves_the_preflight",
    "M4683": f"{_R}::test_the_run_commands_say_their_callers_as_roles",
    "M4684": f"{_R}::test_the_0911_chronology_is_composed_again",
    "M4685": f"{_R}::test_the_h0_reader_sends_back_names_never_ids",
}
