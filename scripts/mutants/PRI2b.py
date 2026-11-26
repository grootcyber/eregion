"""PRI2b (#1225): the push to Imladris reads `assets:` as the watch reads it, writes the format Imladris's release
reads (the version guard), migrates Imladris at the push and back, never lowers a level, and says what the watch
of Imladris will read (docs/design/classification.md, §5.5, §5.6; PR4, PR5). M7827–M7840, measured by
tests/unit/test_host_config_assets.py. BL1c's M54, M2363–M2366, M2368, M2369, M2781, M2782 and M2784 (ten) re-anchored on the new
reading (scripts/mutation_check.py), their sense unchanged. M7861–M7865 from its review."""
HCF = "infra/glorfindel-host/host_config.py"
_T = "tests/unit/test_host_config_assets.py::"

MUTANTS = [
    # The two readers (PR5).
    ("M7827", "both formats in one file read by the push: a file the watch refuses kept, or pushed (PRI2b)", HCF,
     '    if "autonomy" in cfg and "assets" in cfg:\n'
     '        return "of an unknown shape (assets: and the former autonomy: in one file, both formats)"\n',
     ""),
    ("M7828", "the same match twice accepted by the push: Imladris's levels kept from a file its watch refuses "
     "(PRI2b)", HCF,
     '        if a["match"].lower() in seen:\n',
     "        if False:\n"),
    ("M7829", "an entry that says nothing accepted by the push, as the watch never would (PRI2b)", HCF,
     '    if "mode" not in a and "priority" not in a:\n        return "says nothing: neither a mode nor a priority"\n',
     ""),
    # Never a level lowered (PR4).
    ("M7830", "a workstation's level that lowers Imladris's pushed: vm-erp-qa standard under vm-erp-* essential "
     "(PRI2b, PR4)", HCF,
     "        if lowered := _lowered(h0_rules, list(pushed.values()), cited):\n",
     '        if lowered := "":\n'),
    ("M7831", "a workstation's pattern that says standard pushed: a VM no name shows lowered (PRI2b, the safe side)",
     HCF,
     "    if level == STANDARD and _is_pattern(name):\n",
     "    if False:\n"),
    ("M7832", "a quiet from the workstation pushed: quiet no longer comes from Imladris only (PRI2b)", HCF,
     "    if level == QUIET:\n",
     "    if False:\n"),
    ("M7833", "Imladris's patterns lose their level at the push: vm-erp-* essential gone, its VMs lowered (PRI2b, "
     "PR4)", HCF,
     '        if r.get("priority") is not None:\n            e["priority"]',
     '        if r.get("priority") is not None and not _is_pattern(r["match"]):\n            e["priority"]'),
    # The version guard.
    ("M7834", "a release before the guard read as one that reads assets: — its watch refuses the file pushed "
     "(PRI2b)", HCF,
     "        if tuple(int(g) for g in m.groups()) < ASSETS_SINCE:\n",
     "        if False:\n"),
    ("M7835", "a release that does not read (a commit, no label) taken for one that reads assets: (PRI2b)", HCF,
     "        if m is None:\n            return False,",
     "        if m is None:\n            continue\n            return False,"),
    ("M7836", "assets: written toward a release that does not read it: every VM of Imladris in human_only (PRI2b)",
     HCF,
     '    fmt = "assets" if reads_assets and to != "autonomy" else "autonomy"\n',
     '    fmt = "assets" if to != "autonomy" else "autonomy"\n'),
    # The migration at the push, and the way back.
    ("M7837", "Imladris left in autonomy: by a push toward a release that reads assets: (PRI2b)", HCF,
     '    fmt = "assets" if reads_assets and to != "autonomy" else "autonomy"\n',
     '    fmt = "assets" if reads_assets and to != "autonomy" and (h0 is None or "assets" in h0) else "autonomy"\n'),
    ("M7838", "--to autonomy not heard: no way back to a release that does not read assets: (PRI2b)", HCF,
     '    fmt = "assets" if reads_assets and to != "autonomy" else "autonomy"\n',
     '    fmt = "assets" if reads_assets else "autonomy"\n'),
    # HUMAN_ONLY=1.
    ("M7839", "HUMAN_ONLY=1 drops Imladris's levels: the emergency gesture touches the priorities (PRI2b)", HCF,
     '        if r.get("priority") is not None:\n            e["priority"]',
     '        if r.get("priority") is not None and not human_only:\n            e["priority"]'),
    # The report.
    ("M7840", "the report read on what was meant, not on what is written: « kept » for what Imladris will not read "
     "(PRI2b)", HCF,
     "    written = rules_of(out)\n",
     "    written = [*h0_rules, *local]\n"),
]
TESTS = {
    "M7827": (_T + "test_both_formats_on_imladris_keep_nothing "
              + _T + "test_a_workstation_config_the_watch_refuses_is_never_pushed"),
    "M7828": _T + "test_an_imladris_config_the_watch_refuses_keeps_nothing_of_it",
    "M7829": _T + "test_an_imladris_config_the_watch_refuses_keeps_nothing_of_it",
    "M7830": _T + "test_a_workstation_level_that_lowers_imladris_is_not_pushed_and_said",
    "M7831": _T + "test_a_workstation_pattern_that_says_standard_is_never_pushed",
    "M7832": _T + "test_quiet_comes_from_imladris_only",
    "M7833": _T + "test_imladris_s_levels_are_kept_its_patterns_and_reasons_included",
    "M7834": _T + "test_the_release_is_read_where_the_cd_reads_it",
    "M7835": _T + "test_the_release_is_read_where_the_cd_reads_it",
    "M7836": _T + "test_an_old_or_unreadable_release_receives_the_former_format_never_bolder",
    "M7837": _T + "test_imladris_in_autonomy_is_migrated_by_the_push_at_equal_values",
    "M7838": _T + "test_the_way_back_writes_the_former_format_by_the_same_conversion",
    "M7839": _T + "test_human_only_is_never_blocked_and_leaves_the_levels",
    "M7840": _T + "test_the_report_never_says_kept_for_what_imladris_will_refuse",
}

# The review of PRI2b (M7861–M7865).
MAKE = "Makefile"
_C = "tests/unit/test_host_console.py::"
MUTANTS += [
    ("M7861", "a workstation's config unread pushed as an empty one: Imladris's backends and exceptions taken away "
     "(PRI2b review)", HCF,
     "    if text is None or not text.strip():\n"
     "        raise Refused(\"the workstation's config unread (absent, empty or not UTF-8): nothing sent\")\n",
     "    if text is None or not text.strip():\n        return {}\n"),
    ("M7862", "Imladris in assets: on a release unread: its essentials lost in silence (PRI2b review)", HCF,
     '        if not reads_assets and "assets" in h0 and not refusal(h0, True):\n',
     "        if False:\n"),
    ("M7863", "the push never reads Imladris's release: the version guard blind, the former format always "
     "(PRI2b review)", MAKE,
     "\t $(call HOST_RELEASE_READ,$$rel); \\\n",
     "\t : > $$rel; \\\n"),
    ("M7864", "a workstation's config the watch refuses pushed all the same, its entries dropped (PRI2b review)",
     HCF,
     "    if not human_only:\n"
     "        raise Refused(f\"the workstation's config is {why}: the watch would refuse it — nothing sent\")\n",
     ""),
    ("M7865", "IMLADRIS_CONFIG_FORMAT heard from the environment: every later push the way back (PRI2b review)",
     MAKE,
     '\t@case "$(origin IMLADRIS_CONFIG_FORMAT)" in environment*)',
     '\t@case "never" in environment*)'),
]
TESTS.update({
    "M7861": _T + "test_a_workstation_config_unread_is_never_pushed",
    "M7862": (_T + "test_imladris_in_assets_on_a_release_unread_keeps_its_levels_never_its_modes "
              + _T + "test_the_push_never_lowers_a_level_nor_makes_a_mode_bolder"),
    "M7863": _C + "test_push_reads_h0_s_config_before_it_sends_its_own",
    "M7864": _T + "test_a_workstation_config_the_watch_refuses_is_never_pushed",
    "M7865": _C + "test_the_way_back_never_comes_from_the_environment",
})
