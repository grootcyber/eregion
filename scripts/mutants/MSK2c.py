"""MSK2c (#798): the TUI shows what a card or a signal says through the CLI's masking (MSK2, MSK3b) — the
steps of a card masked by its id, then cut to 72 characters, never before; its line, its confirmation, the
restore's screen, the RESOURCES panel and the FEED too. M5220–M5224, then M5255–M5258 after the first review, measured by tests/unit/test_tui_masking.py."""
TUI = "glorfindel/tui.py"
_T = "tests/unit/test_tui_masking.py"

MUTANTS = [
    ("M5220", "the TUI shows a card's steps as written: a NSG's id, its subscription with it, on the screen "
     "(MSK2c)", TUI,
     '            step = _shown(str(step), e["resource_id"])\n',
     "            step = str(step)\n"),
    ("M5221", "the TUI masks a step without its commands: « glorfindel release vm (groupe rg) --yes », no "
     "command at all, where the CLI's `pending` says `<groupe>/<nom>` (MSK2c)", TUI,
     '            step = _shown(str(step), e["resource_id"])\n',
     '            step = __import__("glorfindel.masking").masking.ids_masked(str(step))\n'),
    ("M5222", "the card's id no longer teaches its subscription to the TUI: a bare GUID of it in a step shows "
     "when the shell names another (MSK2c)", TUI,
     '            step = _shown(str(step), e["resource_id"])\n',
     "            step = _shown(str(step))\n"),
    ("M5223", "the TUI cuts a step before masking it: a subscription's id across the 72nd character is no "
     "longer whole, and its first characters show (MSK2c)", TUI,
     '            step = _shown(str(step), e["resource_id"])\n'
     '            lines.append(f"    • {step[:72]}\\n", style="dim")\n',
     '            step = _shown(str(step)[:72], e["resource_id"])\n'
     '            lines.append(f"    • {step}\\n", style="dim")\n'),
    ("M5224", "the restore's screen shows an unreadable vault's error as Azure wrote it: its scope names the "
     "subscription (MSK2c)", TUI,
     "_shown(pending['points_error'], rid)[:200]",
     "pending['points_error'][:200]"),
    # Review 1 (#804): two cuts came before the masking — the vault's error at 200 characters, and the
    # restore's output at its last 600 (`restore_plan.failure_text`); a signal's event lacked its id.
    ("M5255", "the vault's error is cut to 200 characters when it is caught, before the masking: a bare GUID "
     "of the subscription across the cut shows its first characters (MSK2c, review)", TUI,
     'pending["points_error"] = f"{type(exc).__name__}: {exc}"',
     'pending["points_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"'),
    ("M5256", "the restore's screen cuts the vault's error before masking it (MSK2c, review)", TUI,
     "_shown(pending['points_error'], rid)[:200]",
     "_shown(pending['points_error'][:200], rid)"),
    ("M5257", "the TUI hands the restore's raw output to `failure_text`: its last 600 characters cut an id "
     "after « /subscriptions/ », and the rest of it passes the masking (MSK2c, review)", TUI,
     '            output = _shown((proc.stdout or "") + (proc.stderr or ""), esc["resource_id"])\n',
     '            output = (proc.stdout or "") + (proc.stderr or "")\n'),
    ("M5258", "a signal's event is masked without the signal's id: a bare GUID of its subscription shows when "
     "the shell names another (MSK2c, review)", TUI,
     '    event = _shown(s.get("event", "unknown"), rid)\n',
     '    event = _shown(s.get("event", "unknown"))\n'),
]
TESTS = {
    "M5220": f"{_T}::test_the_tui_shows_a_step_s_arm_id_by_its_name_and_group",
    "M5221": f"{_T}::test_the_tui_says_a_step_s_command_as_the_cli_s_pending_does",
    "M5222": f"{_T}::test_the_card_s_id_teaches_its_subscription_to_the_tui",
    "M5223": f"{_T}::test_a_step_is_cut_after_its_masking_never_before",
    "M5224": f"{_T}::test_the_restore_screen_masks_an_unreadable_vault_s_error",
    "M5255": f"{_T}::test_an_unreadable_vault_s_error_is_cut_after_its_masking",
    "M5256": f"{_T}::test_an_unreadable_vault_s_error_is_cut_after_its_masking",
    "M5257": f"{_T}::test_what_the_restore_said_is_masked_before_its_last_600_characters_are_kept",
    "M5258": f"{_T}::test_a_signal_s_event_is_masked_by_the_signal_s_id",
}
