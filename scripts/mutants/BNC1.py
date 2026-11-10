"""BNC1 (#682): the bench read by the machine — `make bench-preflight` (the step 0 in one verdict) and
`make bench-report` (a run's chronology, composed alone), read only, no identifier printed.
M4676–M4685, M4706–M4709 and M4730, measured by tests/unit/test_bench_preflight.py and tests/unit/test_bench_report.py."""
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
    # The review's first round: M4706–M4709.
    ("M4706", "the console's own ✗ (no answer, its token refused) taken for a container's line: the "
     "preflight lets the run go with a silent console (BNC1 review)", PRE,
     '    others = [f for f in failed if not re.match(r"(watch|console|bot)\\s+eregion-", f)]\n',
     '    others = [f for f in failed if not re.match(r"(watch|console|bot)\\s", f)]\n'),
    ("M4707", "the reader's container on H0's network: IMDS, a token, the cloud within its reach "
     "(BNC1 review)", SHARED,
     'READER_HARDEN = ("--rm", "-i", "--network", "none", "--read-only",',
     'READER_HARDEN = ("--rm", "-i", "--read-only",'),
    ("M4708", "H0's write on any NIC dated as the target's isolation: bree's block taken for "
     "gondolin's quarantine (BNC1 review)", REP,
     '        net = next((o for o in ops if o["role"] == "h0" and o["op"] == NIC_WRITE and o["resource"] in mine\n',
     '        net = next((o for o in ops if o["role"] == "h0" and o["op"] == NIC_WRITE\n'),
    ("M4709", "the reader sent to H0 over an ssh that accepts any host key (accept-new) (BNC1 review)",
     SHARED,
     '    if not host_key_pinned(base):\n',
     '    if False:\n'),
    # The review's second round.
    ("M4730", "H0's status and CD read through make without a verified host key: the make targets "
     "connect in accept-new (BNC1 review 2)", PRE,
     '    for check in CHECKS:\n        if h0_pinned or check.__name__ not in H0_CHECKS:\n',
     '    for check in CHECKS:\n        if True:\n'),
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
    "M4706": f"{_P}::test_a_silent_console_stops_the_run",
    "M4707": f"{_R}::test_the_h0_reader_runs_in_a_disposable_container_of_the_deployed_image",
    "M4708": f"{_R}::test_the_0911_chronology_is_composed_again",
    "M4709": f"{_R}::test_an_unverified_h0_host_key_sends_nothing",
    "M4730": f"{_P}::test_an_unpinned_host_key_sends_nothing_to_orodruin_nor_h0",
}
