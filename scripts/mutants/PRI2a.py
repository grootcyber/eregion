"""PRI2a (#1219): the section `assets:` and the former `autonomy:` in one model, the priority of a VM (`level_of`),
the class of a change on the model, the writers that keep the file's format, `glorfindel config migrate`, the note
of the former format, PR1's guard of structure (docs/design/classification.md, §5, §6, §8). M7789–M7805 and, from its review, M7821–M7826, measured
by tests/unit/test_config_assets.py and tests/unit/test_priority_boundary.py. PRT2's M7427 and M7428 re-anchored
on the reading and the class they moved to (scripts/mutants/PRT2.py)."""
CFG = "glorfindel/config.py"
ASSETS = "glorfindel/config_assets.py"
CLS = "glorfindel/config_class.py"
EDIT = "glorfindel/config_edit.py"
MIG = "glorfindel/config_migrate.py"
START = "glorfindel/watch/startup.py"
AGENT = "glorfindel/agent.py"
BOT = "glorfindel/bot.py"
_T = "tests/unit/test_config_assets.py::"
_B = "tests/unit/test_priority_boundary.py::"

MUTANTS = [
    ("M7789", "an unknown priority accepted: `priority: critical`, a typo, read as a level (PRI2a)", ASSETS,
     "    if value in VALID_PRIORITIES:\n",
     "    if True:\n"),
    ("M7790", "critical: true ignored in the former format: the reserve of its graves lost (PRI2a)", ASSETS,
     "            assets.append(AutonomyRule(match=match, mode=m, priority=ESSENTIAL if critical else None))\n",
     "            assets.append(AutonomyRule(match=match, mode=m, priority=None))\n"),
    ("M7791", "both formats accepted in one file: two places that say a VM's mode (PRI2a)", ASSETS,
     '    if "autonomy" in data and "assets" in data:\n',
     "    if False:\n"),
    ("M7792", "an entry without a mode screens the VM: classing a VM changes its mode (PRI2a, PR8)", CFG,
     "        mode = _by_specificity([r for r in self.assets if r.mode is not None], asset_name, _most_prudent)\n",
     "        mode = _by_specificity(self.assets, asset_name, _most_prudent)\n"),
    ("M7793", "an entry that says nothing accepted: neither mode nor priority (PRI2a)", ASSETS,
     '        if "mode" not in a and "priority" not in a:\n',
     "        if False:\n"),
    ("M7794", "the priority resolved by the highest, never the exact entry: no exemption possible (PRI2a, Q6)", CFG,
     "        level = _by_specificity([r for r in self.assets if r.priority is not None], asset_name, _highest)\n",
     "        level = max((r.priority for r in self.assets if r.priority is not None and r.matches(asset_name)), "
     "key=_LEVEL_RANK.get, default=None)\n"),
    ("M7795", "two entries tied on a VM give the lowest level (PRI2a, Q6)", CFG,
     "    return max(rules, key=lambda r: _LEVEL_RANK.get(r.priority, -1)).priority\n",
     "    return min(rules, key=lambda r: _LEVEL_RANK.get(r.priority, -1)).priority\n"),
    ("M7796", "a pattern's priority ignored: `vm-erp-*: essential` makes no VM essential (PRI2a)", CFG,
     "        level = _by_specificity([r for r in self.assets if r.priority is not None], asset_name, _highest)\n",
     "        level = _by_specificity([r for r in self.assets if r.priority is not None and not any(c in r.match "
     "for c in '*?[')], asset_name, _highest)\n"),
    ("M7797", "a level lowered classed « tighten »: quiet posed, essential taken away apply as tightenings (PRI2a)",
     CLS,
     "        if _LEVEL_RANK[la] > _LEVEL_RANK[lb]:\n",
     "        if _LEVEL_RANK[la] != _LEVEL_RANK[lb]:\n"),
    ("M7798", "the former _critical in place of the class by level: entry by entry, an exact quiet under an "
     "essential pattern is neutral (PRI2a)", CLS,
     "    _priority(b, a, said)\n",
     "    cb = {r.match.lower() for r in b.autonomy.assets if r.critical}\n"
     "    ca = {r.match.lower() for r in a.autonomy.assets if r.critical}\n"
     '    said += [("tighten", f"{k}: critical", False) for k in sorted(ca - cb)]\n'
     '    said += [("relax", f"{k}: no longer critical", False) for k in sorted(cb - ca)]\n'),
    ("M7799", "allow_destructive read on the text at its former path: the migration classed « relax », refused "
     "(PRI2a)", CLS,
     "    if b.autonomy.allow_destructive != a.autonomy.allow_destructive:\n",
     '    if (rb.get("autonomy") or {}).get("allow_destructive") != (ra.get("autonomy") or {}).get('
     '"allow_destructive"):\n'),
    ("M7800", "a pattern's text changed not classed: an essential pattern widened passes as a tightening (PRI2a)",
     CLS,
     "    for key in sorted(gone | come):\n",
     "    for key in sorted(set()):\n"),
    ("M7801", "the way back to the former format writes a bolder mode: an essential pattern takes the mode its "
     "text resolves to (PRI2a, §5.6)", MIG,
     '            entry = {"match": r.match, "mode": HUMAN}\n',
     '            entry = {"match": r.match, "mode": cfg.resolve(r.match)}\n'),
    ("M7802", "a writer that ignores the file's format: the console's mode written in autonomy: in a migrated "
     "file (PRI2a)", EDIT,
     '    return ("assets", "list", "default_mode") if "assets" in (data or {}) else ("autonomy", "assets", '
     '"default")\n',
     '    return ("autonomy", "assets", "default")\n'),
    ("M7803", "decide reads the priority: a reader of level_of outside the closed list (PRI2a, PR1)", AGENT,
     "    # Session --mode pins the GLOBAL default; per-asset rules still win in resolve().\n",
     '    _essential = autonomy.is_critical(str(signal.get("vm_name") or ""))\n'
     "    # Session --mode pins the GLOBAL default; per-asset rules still win in resolve().\n"),
    ("M7804", "the bot reads a priority the card carries (PRI2a, PR1)", BOT,
     '    action, etype = esc.get("action", ""), esc.get("escalation_type", "")\n',
     '    action, etype = esc.get("action", ""), esc.get("escalation_type", "")\n'
     '    _rank = esc.get("priority")\n'),
    ("M7805", "the former format said nowhere at the watch's start: never migrated (PRI2a)", START,
     '        for note in getattr(_autonomy, "notes", []):    # PRI2a: the former format, read until the 1.0\n',
     "        for note in []:\n"),
    # The review of PRI2a (M7821–M7825).
    ("M7821", "a migration that would change the defence written all the same: PR7's net taken away (PRI2a "
     "review)", EDIT,
     '        if said["class"] != "neutral":     # PR7: never a migration that changes a mode or a level\n',
     "        if False:\n"),
    ("M7822", "the dossier imports the level's pieces: PR1 gone round by the constants (PRI2a review)",
     "glorfindel/dossier.py",
     "import hashlib\n",
     "import hashlib\nfrom glorfindel.config import ESSENTIAL  # noqa: F401\n"),
    ("M7823", "both formats in one file: their own problems unsaid, three runs to fix one file (PRI2a review)",
     ASSETS,
     '        _check_assets(sections["assets"], check)        # their own problems said in the same message\n'
     '        _check_autonomy(sections["autonomy"], check)\n',
     ""),
    ("M7824", "the comments inside the former section lost in silence by the migration (PRI2a review)", MIG,
     '        lost = comments_inside(text, _check_layout(text), "autonomy" if to == "assets" else "assets")\n',
     "        lost = False\n"),
    ("M7825", "quiet costs otherwise than standard: its graves draw on the essential VMs' reserve (PRI2a review, "
     "PR1)", "glorfindel/model_budget.py",
     "            critical = bool(envelope == REAL and grave and autonomy is not None and autonomy.is_critical(vm))\n",
     '            critical = bool(envelope == REAL and grave and autonomy is not None and autonomy.level_of(vm) != '
     '"standard")\n'),
    ("M7826", "a config mounted read-only: the migration ends on a traceback, never one sentence (PRI2a review)",
     MIG,
     "    except OSError as exc:              # a config mounted read-only (EROFS), or not ours to write (EACCES)\n",
     "    except ZeroDivisionError as exc:\n"),
]
TESTS = {
    "M7789": _T + "test_an_unknown_priority_is_refused_named_and_all_problems_said_at_once",
    "M7790": _T + "test_the_former_format_is_read_in_the_same_model_with_its_note",
    "M7791": _T + "test_both_formats_in_one_file_are_refused_even_when_they_agree",
    "M7792": (_T + "test_a_priority_alone_never_screens_the_vm_from_a_pattern_s_mode "
              + _T + "test_pr8_an_entry_without_a_mode_changes_no_mode_and_one_without_a_priority_no_level"),
    "M7793": _T + "test_an_entry_that_says_nothing_and_a_match_written_twice_are_refused",
    "M7794": _T + "test_the_priority_takes_the_exact_entry_then_the_longest_pattern_tied_the_highest",
    "M7795": _T + "test_the_priority_takes_the_exact_entry_then_the_longest_pattern_tied_the_highest",
    "M7796": _T + "test_the_priority_takes_the_exact_entry_then_the_longest_pattern_tied_the_highest",
    "M7797": _T + "test_a_level_down_relaxes_up_tightens_name_by_name_and_quiet_relaxes_by_prudence",
    "M7798": _T + "test_a_level_down_relaxes_up_tightens_name_by_name_and_quiet_relaxes_by_prudence",
    "M7799": _T + "test_the_migration_is_neutral_and_merges_the_duplicates_said",
    "M7800": _T + "test_a_pattern_s_text_changed_relaxes_and_fewer_essential_entries_too",
    "M7801": _T + "test_the_way_back_to_the_former_format_never_writes_a_bolder_mode",
    "M7802": _T + "test_the_writers_keep_the_file_s_format_never_migrating_it",
    "M7803": _B + "test_the_priority_is_read_only_by_the_closed_list",
    "M7804": _B + "test_decide_and_the_bot_never_read_a_priority_the_data_carries",
    "M7805": _T + "test_the_watch_says_the_former_format_at_its_start_and_counts_only_the_modes",
    "M7821": _T + "test_a_migration_that_would_change_the_defence_is_refused_nothing_written",
    "M7822": _B + "test_the_level_s_pieces_and_a_rule_s_field_are_read_only_by_the_closed_list",
    "M7823": _T + "test_both_formats_in_one_file_are_refused_even_when_they_agree",
    "M7824": _T + "test_the_command_says_the_comments_inside_the_former_section_are_not_carried_over",
    "M7825": _T + "test_pr1_quiet_and_standard_give_the_same_verdict_and_buckets_at_any_state_of_the_count",
    "M7826": _T + "test_a_config_that_can_t_be_written_is_said_in_one_sentence_nothing_written",
}
