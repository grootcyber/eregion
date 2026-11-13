"""MSK2c (#798): the TUI shows what a card or a signal says through the CLI's masking (MSK2, MSK3b) — the
steps of a card masked by its id, then cut to 72 characters, never before; its line, its confirmation, the
restore's screen, the RESOURCES panel and the FEED too. M5220–M5224, measured by tests/unit/test_tui_masking.py."""
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
     "{_shown(pending['points_error'], rid)}",
     "{pending['points_error']}"),
]
TESTS = {
    "M5220": f"{_T}::test_the_tui_shows_a_step_s_arm_id_by_its_name_and_group",
    "M5221": f"{_T}::test_the_tui_says_a_step_s_command_as_the_cli_s_pending_does",
    "M5222": f"{_T}::test_the_card_s_id_teaches_its_subscription_to_the_tui",
    "M5223": f"{_T}::test_a_step_is_cut_after_its_masking_never_before",
    "M5224": f"{_T}::test_the_restore_screen_masks_an_unreadable_vault_s_error",
}
