"""SEC-Fd (#908): the whole TUI never hands a control character to the terminal — the RESOURCES
panel (a resource's name, a block's IP), the FEED (its title, a file of runs/ refused), the
restore's confirmation (its moment, its warning, an unreadable vault's error, a point's time), the
moment typed and the `revert` command. The FEED's two mutants bring back what was there: the
markup escaped, the control characters handed on. M6321–M6330, measured by
tests/unit/test_outside_markup.py."""
TUI = "glorfindel/tui.py"
_T = "tests/unit/test_outside_markup.py"
_ESC_ONLY = "from rich.markup import escape as _esc_markup\nfrom rich.panel import Panel\n"

MUTANTS = [
    ("M6321", "the TUI's RESOURCES panel says a resource's name raw (SEC-Fd, the defect back)", TUI,
     'lines.append(f"  {_literal(_name_said(resource_id))}\\n", style="bold white")',
     'lines.append(f"  {_name_said(resource_id)}\\n", style="bold white")'),
    ("M6322", "the TUI's RESOURCES panel says a block's IP raw (SEC-Fd, the defect back)", TUI,
     "lines.append(f\"  {_literal(b['ip'])}  {age} ago\\n\", style=\"dim\")",
     "lines.append(f\"  {b['ip']}  {age} ago\\n\", style=\"dim\")"),
    ("M6323", "the TUI's FEED title only escapes a run's name: its control characters reach the "
     "terminal (SEC-Fd, the defect back)", TUI,
     ("from rich.panel import Panel\n", '[dim]{_outside(run_label)}[/dim]"'),
     (_ESC_ONLY, '[dim]{_esc_markup(run_label)}[/dim]"')),
    ("M6324", "the TUI's FEED only escapes the name of a file of runs/ refused: its control "
     "characters reach the terminal (SEC-Fd, the defect back)", TUI,
     ("from rich.panel import Panel\n", "refused.append(f\"[yellow]⚠ {_outside(path.name)}: "),
     (_ESC_ONLY, "refused.append(f\"[yellow]⚠ {_esc_markup(path.name)}: ")),   # re-anchored (ENG1a)
    ("M6325", "the TUI's restore confirmation says its moment raw (SEC-Fd)", TUI,
     "lines.append(f\"  Before {_literal(pending['before'])}\\n\", style=\"bold cyan\")",
     "lines.append(f\"  Before {pending['before']}\\n\", style=\"bold cyan\")"),
    ("M6326", "the TUI's restore confirmation says its warning raw (SEC-Fd)", TUI,
     "lines.append(f\"  ⚠ {_literal(_shown(pending['warning'], rid))}\\n\", style=\"yellow\")",
     "lines.append(f\"  ⚠ {_shown(pending['warning'], rid)}\\n\", style=\"yellow\")"),
    ("M6327", "the TUI's restore confirmation says an unreadable vault's error raw (SEC-Fd)", TUI,
     "{_literal(_shown(pending['points_error'], rid)[:200])}",
     "{_shown(pending['points_error'], rid)[:200]}"),
    ("M6328", "the TUI's restore confirmation says a recovery point's time raw (SEC-Fd)", TUI,
     "lines.append(f\"  {_literal(str(p.get('time')))}",
     "lines.append(f\"  {str(p.get('time'))}"),
    ("M6329", "the TUI's restore says the moment's field raw (SEC-Fd)", TUI,
     'lines.append(_literal(pending["buffer"]) + "▌\\n", style="bold cyan")',
     'lines.append(pending["buffer"] + "▌\\n", style="bold cyan")'),
    ("M6330", "the TUI's revert command says its VM raw (SEC-Fd)", TUI,
     '                _literal(f"    → glorfindel revert {vm_arg} --yes\\n"), style="dim cyan"\n',
     '                f"    → glorfindel revert {vm_arg} --yes\\n", style="dim cyan"\n'),
]
TESTS = {
    "M6321": f"{_T}::test_the_tui_s_resources_never_hand_a_control_character_to_the_terminal",
    "M6322": f"{_T}::test_the_tui_s_resources_never_hand_a_control_character_to_the_terminal",
    "M6323": f"{_T}::test_the_tui_s_feed_never_hands_a_control_character_to_the_terminal",
    "M6324": f"{_T}::test_the_tui_s_feed_never_hands_a_control_character_to_the_terminal",
    "M6325": f"{_T}::test_the_tui_s_restore_confirmation_never_hands_a_control_character_to_the_terminal",
    "M6326": f"{_T}::test_the_tui_s_restore_confirmation_never_hands_a_control_character_to_the_terminal",
    "M6327": f"{_T}::test_the_tui_s_restore_confirmation_never_hands_a_control_character_to_the_terminal",
    "M6328": f"{_T}::test_the_tui_s_restore_confirmation_never_hands_a_control_character_to_the_terminal",
    "M6329": f"{_T}::test_the_tui_s_moment_typed_never_hands_a_control_character_to_the_terminal",
    "M6330": f"{_T}::test_the_tui_s_revert_command_never_hands_a_control_character_to_the_terminal",
}
